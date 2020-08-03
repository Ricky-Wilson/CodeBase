#!/usr/bin/env python3

from whoosh import scoring
from whoosh.index import open_dir
from whoosh.qparser import QueryParser

ix = open_dir("indexdir")


def search(query_str, top=10):
    with ix.searcher(weighting=scoring.Frequency) as searcher:
        query = QueryParser("title", ix.schema).parse(query_str)
        for result in searcher.search(query, limit=top):
            print(result["title"])
        # print(results[i]['title'], str(results[i].score), results[i]['textdata'])


all_docs = ix.searcher().documents()
for d in all_docs:
    print(d)
