import requests

class BingSearch(object):
    def __init__(self, sub_key: str) -> None:
        self.sub_key = sub_key
        self._headers = {"Ocp-Apim-Subscription-Key": self.sub_key}
        self._params = {"q": "", "textDecorations": True,
                        "textFormat": "HTML", "mkt": "zh-CN"}
        self._search_url = "https://api.bing.microsoft.com/v7.0/search"

    def search(self, q, mkt="zh-CN"):
        if not q:
            return []
        self._params["q"] = q
        self._params["mkt"] = mkt
        response = requests.get(
            self._search_url, headers=self._headers, params=self._params)
        response.raise_for_status()
        return response.json()['webPages']
    
if __name__ == "__main__":
    bing = BingSearch("c708ee5eda474c93b8b515ae07654941")
    result = bing.search("优质快网络技术咨询（上海）有限公司")
    print(result)