import unittest

from fap_v87_02_gateway import IntentOrgan, WeatherOrgan


class V8702IntentTests(unittest.TestCase):
    def setUp(self):
        self.intent = IntentOrgan()

    def test_date_question(self):
        self.assertEqual(self.intent.classify("今日は何日ですか？").name, "datetime")

    def test_weather_beats_today_modifier(self):
        self.assertEqual(self.intent.classify("今日の天気は？").name, "weather")

    def test_image_capability(self):
        self.assertEqual(self.intent.classify("リンゴを画像生成できますか？").name, "image_capability")

    def test_image_generation(self):
        self.assertEqual(self.intent.classify("赤いリンゴを写真風で生成して").name, "image_generate")

    def test_weather_without_location_does_not_treat_today_as_location(self):
        w = WeatherOrgan()
        self.assertEqual(w.location_from("今日の天気は？"), "")


if __name__ == "__main__":
    unittest.main()
