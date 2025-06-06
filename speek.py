import piper
import wave
import soundfile as sf
import sounddevice as sd

class PiperTTS:
    def __init__(self, model_path = "voice_models/ru_RU/irina/ru_RU-irina-medium.onnx", config_path = "voice_models/ru_RU/irina/ru_RU-irina-medium.onnx.json"):
        self.model_path = model_path
        self.config_path = config_path
        self.tts = piper.PiperVoice.load(self.model_path, self.config_path)
        # В новых версиях sample_rate прямо в self.tts.config
        self.sample_rate = getattr(self.tts.config, "sample_rate", 22050)

    def say(self, text, output_wav="output.wav", play=True):
        with wave.open(output_wav, "wb") as wav_file:
            self.tts.synthesize(text, wav_file)
        print(f"Сохранено в {output_wav}")
        if play:
            audio, sr = sf.read(output_wav, dtype='float32')
            sd.play(audio, sr)
            sd.wait()

# Пример использования
if __name__ == "__main__":
    tts = PiperTTS()
    tts.say("Привет! Это голос Ирины. Как дела?")

