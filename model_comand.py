import requests
import json
import re
import logging
from typing import Dict, Any, Optional, Union

class DroneCommandParser:
    """Упрощенный класс для обработки базовых команд управления дроном"""
    
    def __init__(self, debug: bool = False):
        # Настройка логгера
        self.logger = logging.getLogger("DroneCommandParser")
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            file_handler = logging.FileHandler("drone_command.log")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            self.logger.addHandler(stream_handler)

        # Конфигурация API
        self.OLLAMA_URL = "http://localhost:11434/api/generate"
        self.MODEL_NAME = "llama3.2:3b"
        
        # Сокращенный список основных команд
        self.COMMANDS = [
            # Основные команды движения
            {
                "пример": "взлетай на 2 метра", 
                "команда": "takeoff", 
                "параметры": {"height": "2"},
                "синонимы": ["взлетай", "поднимись", "старт", "взлет"]
            },
            {
                "пример": "лети вперёд 3 метра", 
                "команда": "move_forward", 
                "параметры": {"distance": "3"},
                "синонимы": ["вперед", "прямо", "вперёд", "двигайся вперед"]
            },
            {
                "пример": "лети назад 1 метр", 
                "команда": "move_backward", 
                "параметры": {"distance": "1"},
                "синонимы": ["назад", "двигайся назад", "отступи"]
            },
            {
                "пример": "лети влево 2 метра", 
                "команда": "move_left", 
                "параметры": {"distance": "2"},
                "синонимы": ["влево", "налево", "двигайся влево"]
            },
            {
                "пример": "лети направо 2 метра", 
                "команда": "move_right", 
                "параметры": {"distance": "2"},
                "синонимы": ["направо", "вправо", "двигайся вправо"]
            },
            {
                "пример": "поднимись выше на 1 метр", 
                "команда": "move_up", 
                "параметры": {"distance": "1"},
                "синонимы": ["вверх", "выше", "поднимись"]
            },
            {
                "пример": "опустись на 0.5 метра", 
                "команда": "move_down", 
                "параметры": {"distance": "0.5"},
                "синонимы": ["вниз", "ниже", "опустись"]
            },
            {
                "пример": "садись", 
                "команда": "land", 
                "параметры": {},
                "синонимы": ["посадка", "приземлись", "заверши полет"]
            },
            
            # Команды ориентации
            {
                "пример": "повернись на 90 градусов", 
                "команда": "rotate", 
                "параметры": {"angle": "90"},
                "синонимы": ["поверни", "развернись", "поворот"]
            },
            {
                "пример": "стабилизируй положение", 
                "команда": "stabilize", 
                "параметры": {},
                "синонимы": ["стабилизация", "держи позицию"]
            },
            
            # Навигационные команды
            {
                "пример": "лети к координатам 45.123, 54.321", 
                "команда": "fly_to_coordinates", 
                "параметры": {"latitude": "45.123", "longitude": "54.321"},
                "синонимы": ["координаты", "навигация по gps", "лети к точке"]
            },
            {
                "пример": "вернись домой", 
                "команда": "return_to_home", 
                "параметры": {},
                "синонимы": ["домой", "возврат", "вернись к старту"]
            },
            {
                "пример": "следуй за мной", 
                "команда": "follow_me", 
                "параметры": {},
                "синонимы": ["следуй", "за мной", "сопровождение"]
            },
            
            # Основные настройки
            {
                "пример": "установи скорость 5 м/с", 
                "команда": "set_speed", 
                "параметры": {"speed": "5"},
                "синонимы": ["скорость", "измени скорость"]
            },
            {
                "пример": "зависни", 
                "команда": "hover", 
                "параметры": {"duration": "10"},
                "синонимы": ["зависни", "парить", "держать позицию"]
            }
        ]
        
        # Словарь для быстрого доступа к командам
        self.COMMAND_MAP = {}
        for cmd in self.COMMANDS:
            for synonym in cmd["синонимы"]:
                self.COMMAND_MAP[synonym.lower()] = cmd["команда"]
            self.COMMAND_MAP[cmd["команда"].lower()] = cmd["команда"]
        
        # Валидные параметры команд
        self.VALID_PARAMS = {
            "takeoff": ["height"],
            "move_forward": ["distance"],
            "move_backward": ["distance"],
            "move_left": ["distance"],
            "move_right": ["distance"],
            "move_up": ["distance"],
            "move_down": ["distance"],
            "land": [],
            "rotate": ["angle"],
            "stabilize": [],
            "fly_to_coordinates": ["latitude", "longitude"],
            "return_to_home": [],
            "follow_me": [],
            "set_speed": ["speed"],
            "hover": ["duration"]
        }

        # Значения по умолчанию
        self.DEFAULT_PARAMS = {
            "takeoff": {"height": "2"},
            "move_forward": {"distance": "1"},
            "move_backward": {"distance": "1"},
            "move_left": {"distance": "1"},
            "move_right": {"distance": "1"},
            "move_up": {"distance": "1"},
            "move_down": {"distance": "1"},
            "rotate": {"angle": "90"},
            "set_speed": {"speed": "3"},
            "hover": {"duration": "10"}
        }

    def make_context(self, user_command: str) -> str:
        """Формирует контекст для распознавания команды."""
        context = (
            "Ты - система управления дроном. Твоя задача - понять команду и преобразовать её в формальный запрос.\n\n"
            "Доступные команды:\n"
        )
        
        for cmd in self.COMMANDS:
            context += f"- {cmd['команда']}: {cmd['пример']}\n"
        
        context += (
            "\nФормат ответа ТОЛЬКО JSON:\n"
            "{\"команда\": \"название\", \"параметры\": {\"параметр\": \"значение\"}}\n\n"
            "Правила:\n"
            "1. Сопоставь команду с доступными действиями\n"
            "2. Извлекай числа из текста\n"
            "3. Если параметр не указан, используй значение по умолчанию\n"
            "4. Если команда не распознана, верни 'unknown'\n"
            f"Команда: \"{user_command}\"\n"
        )
        return context

    def extract_json_from_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Извлекает JSON из текста ответа."""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                return json.loads(json_match.group(0))
            return None
        except (json.JSONDecodeError, TypeError):
            return None

    def extract_command_from_text(self, text: str) -> Optional[str]:
        """Извлекает команду из текста по ключевым словам."""
        text = text.lower()
        for keyword, command in self.COMMAND_MAP.items():
            if keyword in text:
                return command
        return None

    def extract_number_from_text(self, text: str) -> Optional[Union[str, float]]:
        """Извлекает числовое значение из текста."""
        num_match = re.search(r'\d+\.?\d*', text)
        if num_match:
            return float(num_match.group(0)) if '.' in num_match.group(0) else num_match.group(0)
        
        number_words = {
            "один": 1, "два": 2, "три": 3, "четыре": 4, "пять": 5,
            "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10
        }
        
        for word, num in number_words.items():
            if word in text:
                return num
        
        return None

    def normalize_command(self, command_data: Dict[str, Any], user_command: str) -> Dict[str, Any]:
        """Нормализует команду и параметры."""
        cmd = command_data.get("команда", "").lower()
        
        if cmd == "unknown" or cmd not in self.VALID_PARAMS:
            extracted_cmd = self.extract_command_from_text(user_command)
            if extracted_cmd:
                cmd = extracted_cmd
            else:
                return {"команда": "unknown", "параметры": {}}
        
        # Применяем параметры по умолчанию
        normalized_params = self.DEFAULT_PARAMS.get(cmd, {}).copy()
        
        # Обновляем параметры из ответа ИИ
        for key, value in command_data.get("параметры", {}).items():
            if key in self.VALID_PARAMS[cmd]:
                normalized_params[key] = value
        
        # Дополнительное извлечение параметров из текста
        if cmd in ["takeoff", "move_forward", "move_backward", "move_left", 
                  "move_right", "move_up", "move_down"]:
            distance = self.extract_number_from_text(user_command)
            if distance:
                normalized_params["distance" if cmd != "takeoff" else "height"] = str(distance)
        
        elif cmd == "rotate":
            angle = self.extract_number_from_text(user_command)
            if angle:
                normalized_params["angle"] = str(angle)
        
        elif cmd == "set_speed":
            speed = self.extract_number_from_text(user_command)
            if speed:
                normalized_params["speed"] = str(speed)
        
        elif cmd == "hover":
            duration = self.extract_number_from_text(user_command)
            if duration:
                normalized_params["duration"] = str(duration)
        
        return {"команда": cmd, "параметры": normalized_params}

    def ollama_query(self, prompt: str) -> Dict[str, Any]:
        """Выполняет запрос к Ollama API."""
        try:
            response = requests.post(
                self.OLLAMA_URL,
                json={
                    "model": self.MODEL_NAME,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1}
                },
                timeout=30
            )
            return response.json()
        except requests.exceptions.RequestException:
            return {"response": ""}

    def parse(self, user_command: str) -> Dict[str, Any]:
        """Анализирует команду и возвращает структурированный результат."""
        self.logger.info(f"Обработка команды: '{user_command}'")
        
        prompt = self.make_context(user_command)
        response = self.ollama_query(prompt)
        ai_response = response.get("response", "")
        
        command_data = self.extract_json_from_response(ai_response) or {}
        normalized_command = self.normalize_command(command_data, user_command.lower())
        
        self.logger.info(f"Результат: {normalized_command}")
        return normalized_command

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Парсер команд дрона')
    parser.add_argument('command', nargs='?', help='Текст команды')
    parser.add_argument('--debug', action='store_true', help='Режим отладки')
    args = parser.parse_args()
    
    parser = DroneCommandParser(debug=args.debug)
    
    if args.command:
        user_command = args.command
    else:
        user_command = input("Введите команду для дрона: ")
    
    result = parser.parse(user_command.strip())
    print("\nРезультат распознавания:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
