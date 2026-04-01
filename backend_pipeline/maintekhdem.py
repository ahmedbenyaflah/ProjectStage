from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from elasticsearch import Elasticsearch
import uvicorn

app = FastAPI(title="Orange Mail Flow API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
es = Elasticsearch("http://localhost:9200")

@app.get("/api/search")
async def search_mail(
    date: str = Query(..., description="Format: YYYY-MM-DD"),
    sender: str = Query(None),
    recipient: str = Query(None),
    qid: str = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, le=1000)
):
    index_name = f"mail-journeys-{date}"
    if not es.indices.exists(index=index_name):
        return {"total": 0, "results": [], "message": "No index for this date."}

    # Calculate Pagination Offset
    start_from = (page - 1) * size

    must_clauses = []
    if sender: must_clauses.append({"match_phrase": {"sender": sender}})
    if recipient: must_clauses.append({"match_phrase": {"recipients": recipient}})
    if qid: must_clauses.append({"term": {"qid.keyword": qid}})

    query = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}

    try:
        response = es.search(
            index=index_name,
            body={
                "query": query,
                "from": start_from,
                "size": size,
                "sort": [{"qid.keyword": "desc"}]
            }
        )
        
        return {
            "total": response["hits"]["total"]["value"],
            "results": [hit["_source"] for hit in response["hits"]["hits"]],
            "page": page,
            "size": size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats(date: str):
    index_name = f"mail-journeys-{date}"
    if not es.indices.exists(index=index_name): return {}
    response = es.search(
        index=index_name,
        body={"size": 0, "aggs": {"status_counts": {"terms": {"field": "status.keyword"}}}}
    )
    return response["aggregations"]["status_counts"]["buckets"]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)