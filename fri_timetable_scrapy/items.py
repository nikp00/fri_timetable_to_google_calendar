# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from scrapy.loader.processors import TakeFirst, MapCompose

import re


def remove_comma(value):
    return " ".join(value).replace(",", "")


def edit_profs(value):
    elements = value.split(",")
    value = ""
    for i, e in enumerate(elements):
        if i % 2 == 0:
            value += e
        else:
            value += e + ", "
    return re.sub(r",*\s$", "", value)


class SubjectItem(scrapy.Item):
    day = scrapy.Field(
        output_processor=TakeFirst()
    )
    time = scrapy.Field(
        input_processor=lambda x: map(lambda y: int(y), x)
    )
    classroom = scrapy.Field(
        output_processor=TakeFirst()
    )
    subject = scrapy.Field(
        output_processor=TakeFirst()
    )
    prof = scrapy.Field(
        input_processor=MapCompose(edit_profs),
        output_processor=TakeFirst()
    )
