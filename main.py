from fastapi import FastAPI,Query
from fastapi.responses import PlainTextResponse
import uvicorn
import asyncio
from QueryWebSearch import *

app = FastAPI()


@app.get("/webSearch", response_class=PlainTextResponse)
async def webSearch(query: list = Query(...)):
    query = query[:3]#最多搜索3个查询
    queryResults = await multyQuerySearch(query, num=4)
    report = ""
    for queryResult in queryResults:
        if queryResult.aiAnswer:
            report += f"【{queryResult.query} AI回复】\n{queryResult.aiAnswer}\n\n"
        for item in queryResult.items:
            if not item.summary:
                continue
            item.summary = item.summary.replace("\n"," ").strip()
            item.title = item.title.replace("\n"," ").strip()
            if (not item.title) or (not item.summary):
                continue
            if len(item.summary)>1000:
                item.summary = item.summary[:1000] + "..."
            if len(item.title)>50:
                item.title = item.title[:50] + "..."
            report += f"【{item.title}】\n{item.summary}\n\n"
    return report

if __name__ == "__main__":
    uvicorn.run("main:app",host="0.0.0.0",port=10003,reload=False)