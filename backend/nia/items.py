import scrapy


class NiaItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    content = scrapy.Field()
    raw_html = scrapy.Field()
    extracted_data = scrapy.Field()
    extraction_method = scrapy.Field()
    spider_name = scrapy.Field()
    crawl_time = scrapy.Field()
    dom_hash = scrapy.Field()
    metadata = scrapy.Field()
