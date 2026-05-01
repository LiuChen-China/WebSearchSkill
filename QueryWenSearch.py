from Browser import *
from typing import List
from Schemas import *
import traceback

async def querySearch(query: str,num=10) -> List[QueryResult]:
    """
    查询搜索结果
    :param query: 搜索关键词
    :return: 搜索结果HTML字符串
    """
    query = query.replace(" ", "+")
    browser = Browser()
    await browser.init_browser()
    await browser.goto(page_id="search", url=f"https://www.sogou.com/web?query={query}")
    divs = await browser.wait_for_elements(selector="//div[contains(@class,'vrwrap')]", page_id="search", timeout=10000)
    text = ''
    items = []
    i = 0
    for div in divs:
        try:
            a = div.locator("a").first
            title = await a.text_content()
            url = await a.get_attribute("href")
            summaryDiv = div.locator("xpath=.//*[contains(@class,'space-txt') or contains(@class,'img-text__content') or contains(@class,'summary')]").first
            if await summaryDiv.count()==0:
                continue
            summary = await summaryDiv.text_content()
            items.append(QueryResult(query=query,title=title,url=url,summary=summary))     
        except Exception as e:
            #traceback.print_exc()
            pass   
    await browser.close()
    return items[:num]

async def multyQuerySearch(queries: List[str], num=10)->List[QueryResult]:
    """
    控制并发数量的批量搜索
    :param queries: 搜索词列表
    :param num: 每个词返回结果数
    :param max_concurrent: 最大并发数
    """
    # 创建多个任务，每个任务会创建自己的浏览器实例
    tasks = [querySearch(query, num) for query in queries]
    # 同时执行所有任务（会同时打开多个浏览器）
    results = await asyncio.gather(*tasks)
    #展开合并结果列表
    results = [item for sublist in results for item in sublist]
    return results


if __name__ == "__main__":
    queries = ["世纪华通", "阿里巴巴"]
    results = asyncio.run(multyQuerySearch(queries))
    print(results)
   