from vosk_drone import VoskSpeechRecognizer
from model_comand import DroneCommandParser
from speek import PiperTTS
import json
import time
import requests
import re
import logging
import os
import soundfile as sf
import sounddevice as sd
import threading
from queue import Queue

class DroneBrain:
    def __init__(self, debug=False):
        self.debug = debug
        self.running = False
        
        # Настройка логгера
        self.logger = logging.getLogger("DroneBrain")
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # Логирование в файл
            file_handler = logging.FileHandler('drone_brain.log')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            # Логирование в консоль
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            self.logger.addHandler(stream_handler)

        # Инициализация компонентов
        self.speech_recognizer = VoskSpeechRecognizer()
        self.command_parser = DroneCommandParser(debug=debug)
        self.tts = PiperTTS()
        
        # Конфигурация LLM
        self.LLM_URL = "http://localhost:11434/api/generate"
        self.MODEL_NAME = "llama3.2:3b"
        
        # Контекст диалога
        self.dialog_context = []
        self.max_context_length = 3
        
        # Состояние системы
        self.activation_phrase = "дрон"  # Ключевое слово для активации
        self.is_active = False  # Флаг активности системы
        self.activation_time = 0  # Время последней активации
        self.last_activity_time = 0  # Время последней активности
        self.activity_timeout = 8.0  # Таймаут неактивности в секундах
        
        # Очередь для обработки команд
        self.command_queue = Queue()
        self.response_queue = Queue()
        
        # Паттерны для классификации
        self.command_pattern = re.compile(
            r'(взлет|лети|двигайся|полет|поднимись|опустись|садись|'
            r'поверни|стабилизируй|координат|скорость|домой|следуй|пари|зависни)',
            re.IGNORECASE
        )
        self.activation_pattern = re.compile(
            r'\b' + re.escape(self.activation_phrase) + r'\b', 
            re.IGNORECASE
        )

    def llm_query(self, prompt, system_prompt=None, json_format=False):
        """Выполняет запрос к LLM с обработкой ошибок и таймаутом"""
        try:
            payload = {
                "model": self.MODEL_NAME,
                "prompt": prompt,
                "system": system_prompt or "Ты - русскоязычная интеллектуальная система управления дроном. Отвечай кратко на то что связанно с дроном, если нет чёткого вопроса, не придумывай лишнего",
                "stream": False,
                "options": {
                    "temperature": 0.5,
                    "num_predict": 50  # Ограничение длины ответа
                }
            }
            
            if json_format:
                payload["format"] = "json"
                
            response = requests.post(
                self.LLM_URL,
                json=payload,
                timeout=15  # Увеличенный таймаут
            )
            response.raise_for_status()
            return response.json().get("response", "")
        except requests.exceptions.Timeout:
            self.logger.warning("LLM запрос превысил таймаут")
            return "Извините, обработка заняла слишком много времени"
        except Exception as e:
            self.logger.error(f"LLM query error: {str(e)}")
            return "Произошла ошибка обработки запроса"

    def update_dialog_context(self, role, content):
        """Обновляет контекст диалога"""
        self.dialog_context.append({"role": role, "content": content})
        
        # Ограничиваем длину контекста
        if len(self.dialog_context) > self.max_context_length:
            self.dialog_context = self.dialog_context[-self.max_context_length:]

    def classify_intent(self, user_input):
        """Определяет тип ввода пользователя с использованием регулярных выражений"""
        # Обновляем время последней активности
        self.last_activity_time = time.time()
        
        # Проверяем активацию
        if self.activation_pattern.search(user_input):
            # Удаляем ключевое слово из команды
            clean_input = self.activation_pattern.sub('', user_input).strip()
            
            # Активируем систему
            if not self.is_active or (time.time() - self.activation_time > 3.0):
                self.is_active = True
                self.activation_time = time.time()
                self.logger.info(f"Система активирована: {user_input}")
                
                # Возвращаем специальный тип для чистого активационного слова
                if not clean_input:
                    return "pure_activation", ""
                
                return "activation", clean_input
        
        # Если система не активирована, игнорируем
        if not self.is_active:
            return "ignore", user_input
        
        # Проверяем команды
        if self.command_pattern.search(user_input):
            return "command", user_input
                
        return "chat", user_input

    def generate_response(self, user_input):
        """Генерирует ответ на основе контекста с оптимизацией"""
        # Формируем историю диалога
        history = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in self.dialog_context[-2:]]  # Берем только последние 2 сообщения
        )
        
        prompt = f"Пользователь: {user_input}\nАссистент:"
        if history:
            prompt = f"{history}\n{prompt}"
        
        system_prompt = (
            "Ты - голосовой ассистент дрона. Отвечай кратко (не более 15 слов). "
            "Используй простой язык. Не упоминай, что ты ИИ."
        )
        
        response = self.llm_query(prompt, system_prompt)
        
        # Очищаем и форматируем ответ
        if response:
            clean_response = response.split("Ассистент:")[-1].strip()
            clean_response = re.sub(r'[\"\{\}\[\]]', '', clean_response)
            
            # Обновляем контекст
            self.update_dialog_context("user", user_input)
            self.update_dialog_context("assistant", clean_response)
            
            return clean_response
        
        return "Не удалось обработать запрос. Пожалуйста, повторите."

    @staticmethod
    def pluralize(number, forms):
        """Склоняет существительные в зависимости от числа"""
        try:
            n = abs(float(number))
        except (TypeError, ValueError):
            return forms[2]  # Множественное число по умолчанию

        n_mod = n % 100
        if 10 <= n_mod <= 20:
            return forms[2]

        n_mod %= 10
        if n_mod == 1:
            return forms[0]
        elif 2 <= n_mod <= 4:
            return forms[1]
        else:
            return forms[2]

    def format_distance(self, distance):
        """Форматирует расстояние с правильным склонением"""
        forms = ['метр', 'метра', 'метров']
        return f"{distance} {self.pluralize(distance, forms)}"

    def format_angle(self, angle):
        """Форматирует угол с правильным склонением"""
        forms = ['градус', 'градуса', 'градусов']
        return f"{angle} {self.pluralize(angle, forms)}"

    def format_duration(self, duration):
        """Форматирует время с правильным склонением"""
        forms = ['секунда', 'секунды', 'секунд']
        return f"{duration} {self.pluralize(duration, forms)}"

    def execute_command(self, command_text):
        """Обрабатывает и выполняет команду"""
        parsed = self.command_parser.parse(command_text)
        
        if parsed["команда"] == "unknown" or not parsed["параметры"]:
            # Если команда неизвестна или нет параметров, возвращаем как chat
            response = self.generate_response(command_text)
            # Если команда неизвестна, генерируем фразу, что команда не распознана
            if parsed["команда"] == "unknown":
                response = f"Не знаю такую команду: '{command_text}'. Попробуйте другую команду."
            return response
        
        cmd = parsed["команда"]
        params = parsed["параметры"]
    
        # Инициализация переменных для форматирования
        height_str = ""
        distance_str = ""
        angle_str = ""
        duration_str = ""
    
        # Форматирование параметров с правильными единицами измерения
        if cmd == "takeoff":
            height = params.get('height', '2')
            height_str = self.format_distance(height)
        elif cmd in ["move_up", "move_down"]:
            distance = params.get('distance', '1')
            distance_str = self.format_distance(distance)
        elif cmd in ["move_forward", "move_backward", "move_left", "move_right"]:
            distance = params.get('distance', '1')
            distance_str = self.format_distance(distance)
        elif cmd == "rotate":
            angle = params.get('angle', '90')
            angle_str = self.format_angle(angle)
        elif cmd == "hover":
            duration = params.get('duration', '10')
            duration_str = self.format_duration(duration)
    
        confirmations = {
            "takeoff": f"Взлетаю на {height_str}",
            "land": "Выполняю посадку",
            "move_forward": f"Лечу вперед на {distance_str}",
            "move_backward": f"Лечу назад на {distance_str}",
            "move_left": f"Лечу влево на {distance_str}",
            "move_right": f"Лечу вправо на {distance_str}",
            "move_up": f"Поднимаюсь на {distance_str}",
            "move_down": f"Опускаюсь на {distance_str}",
            "rotate": f"Поворачиваю на {angle_str}",
            "stabilize": "Стабилизирую положение",
            "fly_to_coordinates": f"Лечу к координатам {params.get('latitude')}, {params.get('longitude')}",
            "return_to_home": "Возвращаюсь к точке взлета",
            "follow_me": "Начинаю следовать за вами",
            "set_speed": f"Устанавливаю скорость {params.get('speed', '3')} м/с",
            "hover": f"Зависаю на {duration_str}"
        }
    
        if cmd in confirmations:
            return confirmations[cmd]
    
        return "Команда принята к выполнению"

    def say(self, text):
        """Озвучивает текст в отдельном потоке"""
        if not text:
            return
            
        self.logger.info(f"Озвучивание: {text}")
        
        def _speak():
            try:
                temp_file = "temp_response.wav"
                self.tts.say(text, play=False, output_wav=temp_file)
                
                if os.path.exists(temp_file):
                    audio, sr = sf.read(temp_file, dtype='float32')
                    sd.play(audio, sr)
                    sd.wait()
                    os.remove(temp_file)
            except Exception as e:
                self.logger.error(f"Ошибка воспроизведения: {str(e)}")
        
        # Запуск в отдельном потоке
        threading.Thread(target=_speak, daemon=True).start()

    def process_input(self, text):
        """Обрабатывает ввод пользователя"""
        if not text:
            self.logger.debug("Пустой ввод пропущен")
            return
        
        # Проверяем наличие слова "дрон" в тексте
        if 'дрон' not in text.lower():
            self.logger.debug("Запрос не содержит слово 'дрон'. Пропускаем.")
            return

        self.logger.info(f"Обработка: '{text}'")
        
        # Определяем тип ввода
        intent, clean_text = self.classify_intent(text)
        self.logger.debug(f"Определен тип: {intent}")
        
        if intent == "ignore":
            self.logger.debug("Игнорируем ввод без активации")
            return
            
        if intent == "pure_activation":
            self.logger.debug("Чистая активация системы")
            self.say("Слушаю вас")
            return
            
        # Обработка в зависимости от типа
        if intent == "activation":
            self.logger.debug("Активация с командой")
            response = self.execute_command(clean_text) if clean_text else "Пожалуйста, дайте команду"
        elif intent == "command":
            response = self.execute_command(clean_text)
        else:
            response = self.generate_response(clean_text)
        
        # Озвучиваем ответ
        if response:
            self.logger.info(f"Ответ: '{response}'")
            self.say(response)

    def check_activity_timeout(self):
        """Проверяет таймаут неактивности и деактивирует систему"""
        if (self.is_active and 
            time.time() - self.last_activity_time > self.activity_timeout):
            self.logger.debug("Деактивация по таймауту")
            self.is_active = False
            self.say("Перехожу в режим ожидания")

    def listen(self):
        """Слушает и распознает речь с обработкой таймаута"""
        try:
            self.logger.debug("Начало прослушивания...")
            text = self.speech_recognizer.start_recognition(
                timeout=15, 
                pause_duration=1.2
            )
            if text:
                self.logger.info(f"Распознано: {text}")
                return text
        except Exception as e:
            self.logger.error(f"Ошибка распознавания: {str(e)}")
        return ""

    def start(self):
        """Запускает систему в основном цикле"""
        self.running = True
        self.activation_time = time.time()
        self.last_activity_time = time.time()
        
        # Приветственное сообщение
        self.say(f"Система управления дроном запущена. Для активации скажите '{self.activation_phrase}'.")
        self.logger.info(f"Система запущена. Активируйте командой '{self.activation_phrase}'")
        
        try:
            while self.running:
                # Проверяем таймаут неактивности
                self.check_activity_timeout()
                
                # Слушаем пользователя
                text = self.listen()
                
                # Обрабатываем распознанный текст
                if text:
                    self.process_input(text)
                
                # Небольшая пауза между циклами
                time.sleep(0.2)
                
        except KeyboardInterrupt:
            self.logger.warning("Получен сигнал прерывания")
        except Exception as e:
            self.logger.critical(f"Критическая ошибка: {str(e)}")
        finally:
            self.stop()

    def stop(self):
        """Останавливает систему"""
        self.running = False
        self.say("Система управления завершает работу.")
        self.logger.info("Система остановлена")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Drone Control System')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    brain = DroneBrain(debug=args.debug)
    brain.start()

