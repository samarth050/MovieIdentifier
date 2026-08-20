class AdultMetadataService:
    """Candidate discovery for vintage/adult film metadata.

    This deliberately searches metadata/index pages only. It does not download
    or stream adult media. IAFD and Adult Film Database are long-running film
    metadata sources; ThePornDB can be enabled through its API when credentials
    are supplied in a future settings option.
    """

    IAFD_DOMAINS = ["iafd.com"]
    AFDB_DOMAINS = ["adultfilmdatabase.com"]

    def __init__(self, web_search):
        self.web = web_search

    def search(self, query, max_results=8):
        results = []
        for source, domains in (
            ("IAFD", self.IAFD_DOMAINS),
            ("Adult Film Database", self.AFDB_DOMAINS),
        ):
            try:
                rows = self.web.search(query, max_results=max_results // 2 or 1, domains=domains)
            except Exception:
                rows = []
            for row in rows:
                results.append({
                    "source": source,
                    "title": row.get("title", ""),
                    "url": row.get("url", ""),
                    "snippet": row.get("snippet", ""),
                    "adult_source": True,
                })
        return results[:max_results]
