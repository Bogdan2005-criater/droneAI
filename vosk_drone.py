import vosk
import json
import queue
import sounddevice as sd
import numpy as np
import time
import threading
import logging

class VoskSpeechRecognizer:
    def __init__(self, model_path="vosk-model-small-ru-0.22", sample_rate=16000):
        """
        Улучшенный распознаватель речи с управлением состоянием
        :param model_path: путь к модели Vosk
        :param sample_rate: частота дискретизации аудио (Гц)
        """
        # Настройка логгера
        self.logger = logging.getLogger("VoskRecognizer")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Логирование в консоль
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(stream_handler)
        
        # Загрузка модели
        self.model = vosk.Model(model_path)
        self.sample_rate = sample_rate
        self.recognizer = vosk.KaldiRecognizer(self.model, sample_rate)
        
        # Очередь для аудиоданных
        self.audio_queue = queue.Queue()
        self.device_info = sd.query_devices(None, 'input')
        
        # Настройки детекции речи
        self.silence_threshold = 300  # Порог тишины (0-32767)
        self.min_phrase_duration = 0.5  # Минимальная длительность фразы (сек)
        self.max_silence_duration = 1.5  # Максимальная длительность тишины для окончания фразы (сек)
        self.min_phrase_volume = 500  # Минимальная громкость для начала фразы
        
        # Управление состоянием распознавания
        self.recognition_enabled = True
        self.lock = threading.Lock()

    def audio_callback(self, indata, frames, time, status):
        """Callback-функция для записи аудио с микрофона"""
        if status:
            self.logger.warning(f"Audio status: {status}")
        
        # Записываем аудио только если распознавание включено
        if self.recognition_enabled:
            self.audio_queue.put(bytes(indata))
        else:
            # Добавляем пустой блок, чтобы не блокировать систему
            self.audio_queue.put(b'')

    def enable_recognition(self):
        """Включает распознавание речи"""
        with self.lock:
            self.recognition_enabled = True
            self.logger.info("Распознавание речи ВКЛЮЧЕНО")

    def disable_recognition(self):
        """Выключает распознавание речи"""
        with self.lock:
            self.recognition_enabled = False
            # Очищаем очередь, чтобы прервать текущее распознавание
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break
            self.logger.info("Распознавание речи ОТКЛЮЧЕНО")

    def is_silence(self, audio_data):
        """Определяет, является ли аудио-блок тишиной"""
        if not audio_data:
            return True
            
        try:
            # Преобразуем байты в массив чисел
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            # Рассчитываем максимальную амплитуду
            max_amplitude = np.max(np.abs(audio_array))
            return max_amplitude < self.silence_threshold
        except Exception as e:
            self.logger.error(f"Ошибка анализа аудио: {str(e)}")
            return True

    def start_recognition(self, timeout=30, pause_duration=1.5):
        """
        Распознавание речи с учетом состояния системы
        :param timeout: максимальное время записи (сек)
        :param pause_duration: минимальная пауза для завершения фразы (сек)
        """
        # Если распознавание отключено, сразу возвращаем пустую строку
        if not self.recognition_enabled:
            return ""
            
        try:
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=8000,
                device=None,
                dtype='int16',
                channels=1,
                callback=self.audio_callback
            ) as stream:
                self.logger.info("Начало распознавания речи...")
                partial_results = []
                silence_frames = 0
                speech_frames = 0
                max_silence_frames = int(pause_duration * self.sample_rate / 8000)
                start_time = time.time()
                is_speaking = False
                last_partial = ""

                while self.recognition_enabled:
                    # Проверка таймаута
                    if time.time() - start_time > timeout:
                        self.logger.info("Таймаут ожидания речи")
                        return ""
                    
                    try:
                        # Получение аудиоблока из очереди с таймаутом
                        data = self.audio_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    
                    # Пропускаем обработку если распознавание было отключено
                    if not self.recognition_enabled:
                        return ""
                    
                    # Детекция начала речи
                    if not is_speaking:
                        if not self.is_silence(data):
                            is_speaking = True
                            speech_frames = 1
                            silence_frames = 0
                    
                    # Обработка данных распознавателем
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        if 'text' in result and result['text']:
                            self.logger.info(f"Распознано: {result['text']}")
                            return result['text']
                    else:
                        # Вывод частичных результатов
                        partial = json.loads(self.recognizer.PartialResult())
                        if 'partial' in partial and partial['partial']:
                            current_partial = partial['partial'].strip()
                            
                            # Фильтрация коротких нерелевантных частичных результатов
                            if (len(current_partial) > 2 and 
                                current_partial != last_partial and 
                                (speech_frames > 2 or len(current_partial.split()) > 1)):
                                
                                self.logger.debug(f"Частично: {current_partial}")
                                partial_results.append(current_partial)
                                last_partial = current_partial
                    
                    # Обновление счетчиков
                    if self.is_silence(data):
                        silence_frames += 1
                        if is_speaking:
                            # Сброс счетчика тишины при очень коротких фразах
                            if speech_frames < 3:
                                silence_frames = 0
                    else:
                        silence_frames = 0
                        speech_frames += 1
                    
                    # Детекция окончания речи
                    if is_speaking and silence_frames > max_silence_frames:
                        # Проверяем, что была достаточно длинная фраза
                        if speech_frames > 10 or (partial_results and len(partial_results[-1].split()) > 1):
                            final_text = partial_results[-1] if partial_results else ""
                            self.logger.info(f"Обнаружено окончание речи: '{final_text}'")
                            return final_text
                        else:
                            # Сбрасываем состояние для новой попытки
                            is_speaking = False
                            silence_frames = 0
                            speech_frames = 0
                            partial_results = []
                            self.logger.debug("Сброс - слишком короткая фраза")

        except KeyboardInterrupt:
            self.logger.warning("Распознавание прервано пользователем")
            return ""
        except Exception as e:
            self.logger.error(f"Ошибка распознавания: {str(e)}")
            return ""
        finally:
            self.logger.info("Завершение распознавания речи")

# Пример использования
if __name__ == "__main__":
    # Настройка логирования для демо
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    recognizer = VoskSpeechRecognizer()
    
    print("Тестирование улучшенного распознавателя речи...")
    print("Скажите что-нибудь...")
    result = recognizer.start_recognition()
    print(f"Финальный результат: {result}")
    
    # Тест отключения распознавания
    print("\nОтключаем распознавание на 5 секунд...")
    recognizer.disable_recognition()
    time.sleep(5)
    
    print("Включаем распознавание обратно...")
    recognizer.enable_recognition()
    
    print("\nСкажите что-нибудь еще...")
    result = recognizer.start_recognition()
    print(f"Финальный результат: {result}")
