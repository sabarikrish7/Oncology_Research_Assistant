import requests
import re
from typing import List, Dict
import logging
import xml.etree.ElementTree as ET
from src.config import PUBMED_MAX_RESULTS, CLINICAL_TRIALS_MAX_RESULTS, NCBI_API_KEY

logger = logging.getLogger(__name__)


class LiveEvidenceFetcher:
    """Phase 5 Component: Fetches real-time data from PubMed and ClinicalTrials.gov APIs."""

    def fetch_latest_pubmed(
        self, query: str, max_results: int = PUBMED_MAX_RESULTS
    ) -> List[Dict[str, str]]:
        try:
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                "db": "pubmed",
                "term": query,
                "retmode": "json",
                "retmax": max_results,
                "sort": "pub_date",
            }
            if NCBI_API_KEY:
                search_params["api_key"] = NCBI_API_KEY

            search_res = requests.get(
                search_url, params=search_params, timeout=10
            ).json()
            id_list = search_res.get("esearchresult", {}).get("idlist", [])

            if not id_list:
                return []

            summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            summary_params = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "rettype": "abstract",
                "retmode": "xml",
            }
            if NCBI_API_KEY:
                summary_params["api_key"] = NCBI_API_KEY

            summary_res = requests.get(
                summary_url, params=summary_params, timeout=10
            )

            root = ET.fromstring(summary_res.content)
            articles = []
            
            for article in root.findall('.//PubmedArticle'):
                pmid_node = article.find('.//PMID')
                if pmid_node is None:
                    continue
                pmid = pmid_node.text

                title_node = article.find('.//ArticleTitle')
                title = title_node.text if title_node is not None else "No Title"

                abstract_texts = article.findall('.//AbstractText')
                abstract = " ".join([node.text for node in abstract_texts if node.text]) if abstract_texts else "No Abstract"

                year_node = article.find('.//PubDate/Year')
                if year_node is not None:
                    year = year_node.text
                else:
                    medline_date = article.find('.//PubDate/MedlineDate')
                    year = medline_date.text[:4] if medline_date is not None else "Unknown Year"

                articles.append(
                    {
                        "source": "PubMed",
                        "id": f"PMID_{pmid}",
                        "text": f"Title: {title}. Abstract: {abstract} Published: {year}",
                    }
                )
            return articles
        except Exception as e:
            logger.error(f"PubMed API Error: {e}")
            return []

    def fetch_clinical_trial(
        self, query: str, max_results: int = CLINICAL_TRIALS_MAX_RESULTS
    ) -> List[Dict[str, str]]:
        """Queries the ClinicalTrials.gov v2 API. Can extract specific NCT IDs or search by condition."""
        try:
            url = "https://clinicaltrials.gov/api/v2/studies"

            # If the query is just an NCT ID, fetch it directly
            nct_match = re.search(r"NCT\d{8}", query.upper())
            if nct_match:
                response = requests.get(f"{url}/{nct_match.group()}", timeout=10)
                studies = [response.json()] if response.status_code == 200 else []
            else:
                params = {
                    "query.cond": query,
                    "pageSize": max_results,
                    "sort": "@relevance",
                }
                response = requests.get(url, params=params, timeout=10)
                studies = response.json().get("studies", [])

            trials = []
            for study in studies:
                protocol = study.get("protocolSection", {})
                nct_id = protocol.get("identificationModule", {}).get(
                    "nctId", "Unknown"
                )
                title = protocol.get("identificationModule", {}).get(
                    "officialTitle", "No Title"
                )
                status = protocol.get("statusModule", {}).get(
                    "overallStatus", "Unknown"
                )
                brief_summary = protocol.get("descriptionModule", {}).get(
                    "briefSummary", "No summary available."
                )
                trials.append(
                    {
                        "source": "ClinicalTrials.gov",
                        "id": nct_id,
                        "text": f"Trial Title: {title}. Status: {status}. Summary: {brief_summary}",
                    }
                )

            return trials
        except Exception as e:
            logger.error(f"ClinicalTrials API Error: {e}")
            return []
