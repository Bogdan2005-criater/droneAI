import random
import json
import time
import logging
import argparse
from typing import List, Dict, Tuple, Any

# Настройка логирования для тестов
test_logger = logging.getLogger("CommandTester")
test_logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
test_logger.addHandler(handler)

# Генератор тестовых команд
def generate_test_cases(num_cases: int = 200) -> List[Tuple[str, Dict]]:
    """Генерирует тестовые случаи с различными формулировками команд"""
    test_cases = []
    
    # Сокращенные команды и их вариации
    command_templates = {
        "takeoff": [
            ("взлетай", {"height": "2"}),
            ("поднимись на {height} метров", {"height": "{height}"}),
            ("стартуем на высоту {height} метр", {"height": "{height}"}),
            ("взлет на {height} м", {"height": "{height}"}),
            ("начать полет на {height} метров", {"height": "{height}"}),
        ],
        "move_forward": [
            ("лети вперед", {"distance": "1"}),
            ("двигайся прямо {distance} метров", {"distance": "{distance}"}),
            ("пролети вперед {distance} метр", {"distance": "{distance}"}),
            ("вперед на {distance} м", {"distance": "{distance}"}),
        ],
        "move_backward": [
            ("лети назад", {"distance": "1"}),
            ("двигайся назад {distance} метров", {"distance": "{distance}"}),
            ("отступи на {distance} метр", {"distance": "{distance}"}),
            ("назад на {distance} м", {"distance": "{distance}"}),
        ],
        "move_left": [
            ("влево", {"distance": "1"}),
            ("двигайся влево {distance} метров", {"distance": "{distance}"}),
            ("сместись влево на {distance} метр", {"distance": "{distance}"}),
            ("налево на {distance} м", {"distance": "{distance}"}),
        ],
        "move_right": [
            ("направо", {"distance": "1"}),
            ("лети вправо {distance} метров", {"distance": "{distance}"}),
            ("сместись вправо на {distance} м", {"distance": "{distance}"}),
        ],
        "move_up": [
            ("вверх", {"distance": "1"}),
            ("поднимись выше на {distance} метров", {"distance": "{distance}"}),
            ("набери высоту {distance} метр", {"distance": "{distance}"}),
        ],
        "move_down": [
            ("вниз", {"distance": "1"}),
            ("опустись на {distance} метров", {"distance": "{distance}"}),
            ("снизь высоту на {distance} метр", {"distance": "{distance}"}),
        ],
        "rotate": [
            ("повернись", {"angle": "90"}),
            ("развернись на {angle} градусов", {"angle": "{angle}"}),
            ("сделай поворот на {angle}°", {"angle": "{angle}"}),
            ("поверни влево", {"angle": "45"}),
            ("развернись против часовой на {angle} градусов", {"angle": "{angle}"}),
            ("левый поворот на {angle}°", {"angle": "{angle}"}),
            ("поверни вправо", {"angle": "45"}),
            ("развернись по часовой на {angle} градусов", {"angle": "{angle}"}),
            ("правый поворот на {angle}°", {"angle": "{angle}"}),
        ],
        "land": [
            ("садись", {}),
            ("приземлись", {}),
            ("иди на посадку", {}),
        ],
        "return_to_home": [
            ("вернись домой", {}),
            ("возвращайся на базу", {}),
            ("лети к точке взлета", {}),
        ],
        "follow_me": [
            ("следуй за мной", {}),
            ("преследуй меня", {}),
            ("двигайся за объектом", {}),
        ],
        "set_speed": [
            ("установи скорость {speed} м/с", {"speed": "{speed}"}),
            ("лети со скоростью {speed} метров в секунду", {"speed": "{speed}"}),
            ("измени скорость на {speed}", {"speed": "{speed}"}),
        ],
        "hover": [
            ("зависни", {"duration": "10"}),
            ("держи позицию {duration} секунд", {"duration": "{duration}"}),
            ("пари на месте {duration} сек", {"duration": "{duration}"}),
        ],
        "fly_to_coordinates": [
            ("лети к координатам {lat}, {lon}", {"latitude": "{lat}", "longitude": "{lon}"}),
            ("навигация на точку {lat} {lon}", {"latitude": "{lat}", "longitude": "{lon}"}),
            ("gps точка {lat} {lon}", {"latitude": "{lat}", "longitude": "{lon}"}),
        ],
        "stabilize": [
            ("стабилизируй положение", {}),
            ("держи позицию", {}),
            ("останови вращение", {}),
        ]
    }
    
    # Генерация случайных тестовых случаев
    commands = list(command_templates.keys())
    number_words = ["один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять", "десять"]
    
    for _ in range(num_cases):
        cmd = random.choice(commands)
        template, params = random.choice(command_templates[cmd])
        
        # Подстановка значений
        if "{height}" in template:
            height = random.choice([str(i) for i in range(1, 11)] + number_words)
            template = template.replace("{height}", height)
            params = {"height": height if height.isdigit() else str(number_words.index(height) + 1)}
        
        elif "{distance}" in template:
            distance = random.choice([str(i) for i in range(1, 11)] + number_words)
            template = template.replace("{distance}", distance)
            params = {"distance": distance if distance.isdigit() else str(number_words.index(distance) + 1)}
        
        elif "{angle}" in template:
            angle = random.choice(["30", "45", "60", "90", "120", "сто восемьдесят"])
            template = template.replace("{angle}", angle)
            params = {"angle": angle if angle.isdigit() else "180"}
        
        elif "{speed}" in template:
            speed = random.choice(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"])
            template = template.replace("{speed}", speed)
            params = {"speed": speed}
        
        elif "{lat}" in template and "{lon}" in template:
            lat = f"{random.uniform(-90, 90):.6f}"
            lon = f"{random.uniform(-180, 180):.6f}"
            template = template.replace("{lat}", lat).replace("{lon}", lon)
            params = {"latitude": lat, "longitude": lon}
        
        elif "{duration}" in template:
            duration = random.choice(["5", "10", "15", "20", "тридцать"])
            template = template.replace("{duration}", duration)
            params = {"duration": duration if duration.isdigit() else "30"}
        
        # Для команд без параметров
        if params == {}:
            expected = {"команда": cmd, "параметры": {}}
        else:
            expected = {"команда": cmd, "параметры": params}
        
        test_cases.append((template, expected))
    
    return test_cases

# Класс для тестирования точности
class CommandAccuracyTester:
    def __init__(self, parser_instance):
        self.parser = parser_instance
        self.test_cases = generate_test_cases()
        self.results = []
        self.stats = {
            "total": 0,
            "correct": 0,
            "command_accuracy": {},
            "processing_time": 0,
            "errors_by_type": {}
        }
    
    def run_tests(self, log_details: bool = False):
        """Запускает все тесты и собирает статистику"""
        start_time = time.time()
        
        for i, (command, expected) in enumerate(self.test_cases):
            # Выполняем анализ команды
            result = self.parser.parse(command)
            
            # Проверяем результат
            is_correct = self._compare_results(result, expected)
            test_result = {
                "id": i + 1,
                "command": command,
                "expected": expected,
                "actual": result,
                "correct": is_correct
            }
            self.results.append(test_result)
            
            # Обновляем статистику
            self.stats["total"] += 1
            if is_correct:
                self.stats["correct"] += 1
            else:
                error_type = self._classify_error(expected, result)
                self.stats["errors_by_type"][error_type] = self.stats["errors_by_type"].get(error_type, 0) + 1
            
            cmd_name = expected["команда"]
            self.stats["command_accuracy"].setdefault(cmd_name, {"total": 0, "correct": 0})
            self.stats["command_accuracy"][cmd_name]["total"] += 1
            if is_correct:
                self.stats["command_accuracy"][cmd_name]["correct"] += 1
            
            if log_details:
                status = "Пройден" if is_correct else "Ошибка"
                test_logger.info(f"Тест #{i+1}: {status}\n"
                                f"Команда: '{command}'\n"
                                f"Ожидалось: {expected}\n"
                                f"Получено:  {result}\n")
        
        # Рассчитываем время выполнения
        self.stats["processing_time"] = time.time() - start_time
        if self.stats["total"] > 0:
            self.stats["accuracy"] = self.stats["correct"] / self.stats["total"] * 100
            self.stats["avg_time"] = self.stats["processing_time"] / self.stats["total"]
        else:
            self.stats["accuracy"] = 0
            self.stats["avg_time"] = 0
        
        # Рассчитываем точность по командам
        for cmd, data in self.stats["command_accuracy"].items():
            if data["total"] > 0:
                data["accuracy"] = data["correct"] / data["total"] * 100
            else:
                data["accuracy"] = 0
    
    def _compare_results(self, actual: Dict, expected: Dict) -> bool:
        """Сравнивает фактические и ожидаемые результаты с учетом погрешностей"""
        # Проверка соответствия команды
        if actual["команда"] != expected["команда"]:
            return False
        
        # Проверка параметров
        actual_params = actual["параметры"]
        expected_params = expected["параметры"]
        
        # Для координат допускаем погрешность
        if expected["команда"] == "fly_to_coordinates":
            try:
                actual_lat = float(actual_params.get("latitude", 0))
                actual_lon = float(actual_params.get("longitude", 0))
                expected_lat = float(expected_params.get("latitude", 0))
                expected_lon = float(expected_params.get("longitude", 0))
                
                # Допустимая погрешность в координатах
                if abs(actual_lat - expected_lat) > 0.001 or abs(actual_lon - expected_lon) > 0.001:
                    return False
                return True
            except:
                return False
        
        # Для других команд сравниваем как есть
        return actual_params == expected_params
    
    def _classify_error(self, expected: Dict, actual: Dict) -> str:
        """Классифицирует тип ошибки"""
        if actual["команда"] == "unknown":
            return "Не распознана команда"
        
        if expected["команда"] != actual["команда"]:
            return "Неправильная команда"
        
        if not expected["параметры"] and actual["параметры"]:
            return "Лишние параметры"
        
        if expected["параметры"] and not actual["параметры"]:
            return "Отсутствуют параметры"
        
        # Проверка конкретных несоответствий параметров
        for key, expected_value in expected["параметры"].items():
            if key not in actual["параметры"]:
                return f"Отсутствует параметр: {key}"
            
            if expected_value != actual["параметры"][key]:
                return f"Неправильное значение параметра: {key}"
        
        return "Другая ошибка"
    
    def generate_report(self) -> Dict:
        """Генерирует подробный отчет о тестировании"""
        return {
            "summary": {
                "total_tests": self.stats["total"],
                "passed_tests": self.stats["correct"],
                "accuracy": f"{self.stats['accuracy']:.2f}%",
                "total_time": f"{self.stats['processing_time']:.2f} сек",
                "avg_time_per_command": f"{self.stats['avg_time']:.4f} сек",
                "error_distribution": self.stats["errors_by_type"]
            },
            "by_command": {
                cmd: {
                    "total": data["total"],
                    "correct": data["correct"],
                    "accuracy": f"{data['accuracy']:.2f}%"
                } for cmd, data in self.stats["command_accuracy"].items()
            },
            "details": self.results[:100]  # Сохраняем только первые 100 результатов для экономии места
        }
    
    def save_report(self, filename: str = "command_accuracy_report.json"):
        """Сохраняет отчет в JSON файл"""
        report = self.generate_report()
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        test_logger.info(f"Отчет сохранен в {filename}")
    
    def print_summary(self):
        """Выводит сводку результатов в консоль"""
        test_logger.info("\n" + "="*60)
        test_logger.info(" ТЕСТИРОВАНИЕ ТОЧНОСТИ РАСПОЗНАВАНИЯ КОМАНД ДРОНА ")
        test_logger.info("="*60)
        
        test_logger.info(f"Всего тестов: {self.stats['total']}")
        test_logger.info(f"Пройдено: {self.stats['correct']}")
        test_logger.info(f"Точность: {self.stats['accuracy']:.2f}%")
        test_logger.info(f"Общее время выполнения: {self.stats['processing_time']:.2f} сек")
        test_logger.info(f"Среднее время на команду: {self.stats['avg_time']:.4f} сек")
        
        test_logger.info("\nТочность по командам:")
        for cmd, data in self.stats["command_accuracy"].items():
            test_logger.info(f"- {cmd:.<20} {data['accuracy']:>5.1f}% "
                            f"({data['correct']}/{data['total']})")
        
        # Распределение ошибок
        if self.stats["errors_by_type"]:
            test_logger.info("\nРаспределение ошибок:")
            for error_type, count in self.stats["errors_by_type"].items():
                test_logger.info(f"- {error_type}: {count} ошибок")
        
        # Анализ ошибок
        errors = [r for r in self.results if not r["correct"]]
        if errors:
            test_logger.info("\nТипичные ошибки (первые 5):")
            for error in errors[:5]:
                test_logger.info(f"Команда: '{error['command']}'")
                test_logger.info(f"Ожидалось: {error['expected']}")
                test_logger.info(f"Получено:  {error['actual']}")
                test_logger.info("-"*50)
        else:
            test_logger.info("\nВсе тесты пройдены успешно!")

# Интеграция с основной системой
if __name__ == "__main__":
    # Импорт основной системы
    from model_comand import DroneCommandParser
    
    parser = argparse.ArgumentParser(description='Тестирование точности распознавания команд дрона')
    parser.add_argument('--test', action='store_true', help='Запустить тестирование точности')
    parser.add_argument('--num', type=int, default=200, help='Количество тестовых случаев')
    parser.add_argument('--debug', action='store_true', help='Включить режим отладки парсера')
    parser.add_argument('--details', action='store_true', help='Показывать детали каждого теста')
    parser.add_argument('--save', action='store_true', help='Сохранить полный отчет в JSON')
    args = parser.parse_args()
    
    if args.test:
        # Создаем экземпляр парсера
        drone_parser = DroneCommandParser(debug=args.debug)
        
        test_logger.info("Генерация тестовых команд...")
        tester = CommandAccuracyTester(drone_parser)
        tester.test_cases = generate_test_cases(num_cases=args.num)
        
        test_logger.info(f"Запуск {len(tester.test_cases)} тестов...")
        tester.run_tests(log_details=args.details)
        
        test_logger.info("Анализ результатов...")
        tester.print_summary()
        
        if args.save:
            tester.save_report()
    else:
        test_logger.info("Пожалуйста, используйте --test для запуска тестов")
