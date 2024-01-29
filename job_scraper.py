import requests
from bs4 import BeautifulSoup
import instructor
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
import os


load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
client = instructor.patch(OpenAI(api_key=api_key))

class JobDetails(BaseModel):
    job_title : str
    job_url : str
    company_id : int
    city : str
    state : str
    country : str
    work_arrangement : str
    salary_lower_bound : str
    salary_upper_bound : str
    salary_frequency : str
    min_qualifications : str

async def extract_job_details(content):
    job: JobDetails = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        response_model=JobDetails,
        messages=[
            {"role": "user", "content": "Extract all possible/specified details for a given job listing of your choice" + str(content)},
        ]
    )
    return job


def scrape_job_posting(url):
    response = requests.get(url)

    if response.status_code == 200:
        print("successfully fetched url")
        # print(response.text)
        soup = BeautifulSoup(response.text, "lxml")
        return soup
        
    else:
        print(f"failed to fetch url, {response.status_code}")
        
async def main():
    url = 'https://webscraper.io/test-sites/e-commerce/allinone'  # Replace with actual URL
    scraped_content = scrape_job_posting(url)
    if scraped_content:
        job_details = await extract_job_details(scraped_content)
        print(job_details)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
