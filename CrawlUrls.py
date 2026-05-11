from HotReloadConfig import config
from trafilatura import extract
from typing import List,Optional
from Browser import *
import asyncio
import json


async def crawlUrls(urls:Optional[List | str] = None)->List[str]:
    if type(urls) == str:
        urls = [urls]
    browser = Browser()
    await browser.init_browser()
    tasks = []
    page_ids = []
    for i, url in enumerate(urls):
        page_id = f"crawl_{i}"
        page_ids.append(page_id)
        tasks.append(browser.goto(url, page_id=page_id))
    await asyncio.gather(*tasks)
    #获得所有网页内容
    tasks = []
    for page_id in page_ids:
        tasks.append(browser.get_page_html(page_id=page_id))
    htmls = await asyncio.gather(*tasks)
    await browser.close()
    summaries = []
    for html in htmls:
        summaries.append(extract(html, output_format="txt", with_metadata=False,no_fallback=True,deduplicate=True))
    return summaries


if __name__ == "__main__":
    urls = [
        'http://mp.weixin.qq.com/s?src=3&timestamp=1777866426&ver=1&signature=3olHzM6NXepHPISVaqB1BQFPgv7LTQApR*9n6Sv2gLs65BBWGKLINUfJA4iK6oXihJ4oZrQKlOIYcX2-OyMapSfqDJ-R1jWjWKaaO-CmlGTsOCKBxGAjmZlXC7lN*z970e-BUgq43VSpCVB*VnQ5*A==', 
        'https://www.sogou.com/link?url=WaeIF24cBDu3hP1y3b24hf4T17ln4fKRt9wdBjT9t9AhSvbAqYRS6SHmfGkNvdZG'
        ]
    asyncio.run(crawlUrls(urls))