import requests
from bs4 import BeautifulSoup
import trafilatura
import logging
import json
from typing import Optional, Dict, List
from playwright.async_api import async_playwright
import time
import unicodedata
import re

# clean_text and extract_website_info remain the same as they don't use playwright
def clean_text(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize('NFKD', str(text))
    cleaned = normalized.encode('ascii', 'ignore').decode('ascii')
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def extract_website_info(url: str, max_retries: int = 3) -> Optional[dict]:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            
            extracted_content = trafilatura.extract(response.text)
            
            if not extracted_content:
                soup = BeautifulSoup(response.text, 'html.parser')
                for script in soup(["script", "style", "nav", "header", "footer"]):
                    script.decompose()
                extracted_content = soup.get_text(separator=' ', strip=True)
            
            if extracted_content:
                cleaned_content = clean_text(extracted_content)
                content_summary = (cleaned_content[:500] + "...") if len(cleaned_content) > 500 else cleaned_content
            else:
                content_summary = ""

            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string if soup.title else "No Title"
            
            return {
                "url": url,
                "title": title,
                "contentSummary": content_summary
            }
        
        except requests.RequestException as e:
            logging.error(f"Request error on attempt {attempt + 1}: {e}")
    
    return None

async def get_paa_questions(query: str, max_initial_questions: int = 10) -> List[Dict[str, List[str]]]:
    """
    Async version of get_paa_questions
    """
    related_questions = []
    global_processed_questions = set()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        try:
            await page.goto("https://www.google.com")
            await page.wait_for_selector('textarea[name="q"]')
            await page.fill('textarea[name="q"]', query)
            await page.keyboard.press('Enter')
            
            await page.wait_for_selector('span.CSkcDe', timeout=10000)
            processed_initial_questions = set()
            
            for _ in range(5):
                for scroll_attempt in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1000)
                
                current_questions = await page.query_selector_all('span.CSkcDe')
                
                if not current_questions:
                    break
                    
                for question in current_questions:
                    if len(related_questions) >= max_initial_questions:
                        break
                    
                    question_text = await question.inner_text()
                    
                    if question_text in processed_initial_questions:
                        continue
                        
                    question_entry = {
                        "initialQuestion": question_text,
                        "relatedQuestions": []
                    }
                    
                    processed_initial_questions.add(question_text)
                    
                    try:
                        await question.click()
                        await page.wait_for_timeout(2000)
                        
                        new_questions = await page.query_selector_all('span.CSkcDe')
                        
                        for new_q in new_questions:
                            new_q_text = await new_q.inner_text()
                            if (new_q_text and 
                                new_q_text not in global_processed_questions and 
                                new_q_text != question_text):
                                question_entry["relatedQuestions"].append(new_q_text)
                                global_processed_questions.add(new_q_text)
                        
                        related_questions.append(question_entry)
                    
                    except Exception as e:
                        logging.error(f"Error processing question '{question_text}': {e}")
                        continue
                
                if len(related_questions) >= max_initial_questions:
                    break
        
        except Exception as e:
            logging.error(f"Error during scraping: {e}")
        
        finally:
            await browser.close()
    
    return related_questions

async def get_search_results(query: str, max_questions: int = 5, max_websites: int = 3):
    """
    Async version of get_search_results
    """
    try:
        related_questions = await get_paa_questions(query, max_questions)
        
        website_contents = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            await page.goto("https://www.google.com")
            await page.wait_for_selector('textarea[name="q"]')
            await page.fill('textarea[name="q"]', query)
            await page.keyboard.press('Enter')
            
            await page.wait_for_selector('div.g')
            search_results = await page.query_selector_all('div.g')
            
            for i in range(min(max_websites, len(search_results))):
                link_element = await search_results[i].query_selector('a')
                if link_element:
                    url = await link_element.get_attribute('href')
                    if url:
                        website_info = extract_website_info(url)
                        if website_info:
                            website_info['website'] = f'Website {i+1}'
                            website_contents.append(website_info)
            
            await browser.close()
        
        result = {
            "relatedQuestions": related_questions,
            "websiteContents": website_contents
        }
        
        return result
    
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None

logging.basicConfig(level=logging.INFO)