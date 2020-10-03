import scrapy
from fri_timetable_scrapy.items import SubjectItem
from scrapy.loader import ItemLoader


class TimetableSpider(scrapy.Spider):
    name = "timetable"

    def __init__(self, *args, **kwargs):
        super(TimetableSpider, self).__init__(*args, **kwargs)
        self.start_urls = [kwargs.get("url")]

    def _parse(self, response):
        days = response.css(".grid-day-column")
        for day in days:
            subjects = day.css(".grid-entry")
            for subject in subjects:
                text = subject.css(".entry-hover").get()
                elements = []
                for e in text.split("\n"):
                    e = e.strip()
                    e = e.replace("<br>", ",")
                    elements.append(e)
                time = elements[1].split(" ")
                elements = elements[1: 3] + elements[4:]

                elements[2] = subject.css(".link-subject::text").get()

                subject_item = ItemLoader(item=SubjectItem(), selector=subject)
                subject_item.add_value("day", time[0])
                subject_item.add_value("time", (time[1][:time[1].index(":")], time[3][:time[3].index(":")]))
                subject_item.add_value("classroom", elements[1])
                subject_item.add_value("subject", elements[2])
                subject_item.add_value("prof", elements[3])

                yield subject_item.load_item()
