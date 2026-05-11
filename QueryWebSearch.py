from Browser import *
from typing import List
from Schemas import *
from CrawlUrls import crawlUrls
from trafilatura import extract
import traceback



async def querySearchUrl(query: str,num=10) -> QueryResult:
    """
    查询搜索结果URL
    :param query: 搜索关键词
    :return: 搜索结果URL列表
    """
    query = query.replace(" ", "+")
    browser = Browser()
    await browser.init_browser()
    url = f'https://cn.bing.com/search?q={query}&qs=n&form=QBRE&sp=-1&lq=0&pq={query}'
    await browser.goto(page_id="search", url=url)
    # bing自带的AI答复
    nodes = await browser.wait_for_elements(selector="//*[contains(@class, 'gs_tkn') or contains(@class, 'acf_t_c_content') or contains(@class, 'cht_text') or contains(@class, 'qna_hpiw')]", page_id="search", timeout=5000,debug=False)
    aiAnswer = ""
    for node in nodes:
        try:
            await node.locator('[class*="gs_cit"], [class*="md_citlink"]').evaluate_all("nodes => nodes.forEach(n => n.remove())")
            html = await node.inner_html(timeout=100)
        except Exception as e:
            #traceback.print_exc() 
            continue
        text = extract(
            f"<html><body>{html}</body></html>",
            output_format="txt",
            with_metadata=False,
            no_fallback=True,
            deduplicate=False,
            include_links=False,
            favor_precision=False,    # 不追求精准过滤
            favor_recall=True         # 尽可能保留所有内容
        )
        text = '' if not text else text
        aiAnswer += text.strip()[:100] + "\n"
    aTags = await browser.wait_for_elements(selector="//a[contains(@h,'ID')]", page_id="search", timeout=10000)
    items = []
    for a in aTags:
        try:
            html = await a.evaluate("el => el.outerHTML",timeout=100)
            title = await a.inner_text(timeout=100)
            if len(title)<10:
                continue
            url = await a.get_attribute("href")
            items.append(QueryItem(query=query,title=title.strip(),url=url,summary=""))     
        except Exception as e:
            #traceback.print_exc() 
            pass
    await browser.close()
    return QueryResult(query=query, aiAnswer=aiAnswer, items=items[:num])

async def multyQuerySearch(queries: List[str], num=5) -> List[QueryResult]:
    """
    控制并发数量的批量搜索
    :param queries: 搜索词列表
    :param num: 每个词返回结果数
    :param max_concurrent: 最大并发数
    """
    # 创建多个任务，每个任务会创建自己的浏览器实例
    tasks = [querySearchUrl(query, num) for query in queries]
    # 同时执行搜索任务（会同时打开多个浏览器）
    queryResults = await asyncio.gather(*tasks)
    # 再同时对所有搜索URL进行爬取
    tasks = []
    for i,queryResult in enumerate(queryResults):
        queryItems = queryResult.items
        urls = [item.url for item in queryItems]
        tasks.append(crawlUrls(urls))
    summariesList = await asyncio.gather(*tasks)
    for i,queryResult in enumerate(queryResults):
        queryItems = queryResult.items
        summaries = summariesList[i]
        for j,item in enumerate(queryItems):
            queryItems[j].summary = summaries[j]
        queryResult.items = queryItems
        queryResults[i] = queryResult
    return queryResults


if __name__ == "__main__":
    queries = ["世纪华通股票代码","KFC三柠气泡美式"]
    results = asyncio.run(multyQuerySearch(queries))
    print(results)
   