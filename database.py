"""
e621 tagger companion - database downloader
Author: AyoKeito
Version: 1.0.1
GitHub: https://github.com/AyoKeito/e621updater-python
To tag stuff, you should know stuff.
"""

import re
import asyncio
import aiohttp
import gzip
import pandas as pd
import argparse
import io

async def download_file(session, url):
    async with session.get(url, headers={'User-Agent': 'e621 tagger'}, proxy=args.proxy) as resp:
        if resp.status == 200:
            return await resp.content.read()

async def download_and_process_csv(url, session):
    async with session.get(url, headers={'User-Agent': 'e621 tagger'}, proxy=args.proxy) as resp:
        if resp.status == 200:
            content = await resp.text()
            file_links = re.findall(r'<a href="(.*?)">', content)
            latest_posts_file = sorted([x for x in file_links if x.startswith("posts")], reverse=True)[0]
            latest_tags_file = sorted([x for x in file_links if x.startswith("tags")], reverse=True)[0]
            try:
                print(f"Downloading and processing {latest_posts_file} and {latest_tags_file}")
                content = gzip.decompress(await download_file(session, url + latest_posts_file))
                df = pd.read_csv(io.BytesIO(content), usecols=["id", "md5", "tag_string"])
                df.to_parquet("posts.parquet", engine='pyarrow', compression='brotli')
                print(f"\033[32mProcessing {latest_posts_file} done!\033[0m")
                del df
                
                content = gzip.decompress(await download_file(session, url + latest_tags_file)).decode()
                df = pd.read_csv(io.StringIO(content), header=0, dtype={"id": int, "name": str, "category": int, "post_count": int})
                df = df[df["category"] == 1][["name"]]
                df.to_parquet("artists.parquet", engine='pyarrow', compression='snappy')
                print(f"\033[32mProcessing {latest_tags_file} done!\033[0m")
                del df
            except Exception as e:
                print(f"An error occurred while processing {latest_posts_file} or {latest_tags_file}:", e)

async def main(url, proxy):
    async with aiohttp.ClientSession() as session:
        await download_and_process_csv(url, session)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Download and process CSV files. Download gz archives, extract & filter irrelevant data, and save as compressed parquet files.")
    parser.add_argument("-p", "--proxy", help="The proxy to use for all network calls (optional). Usage examples: http://proxy.server:8888 or http://user:password@proxy.server:8888")
    args = parser.parse_args()
    try:
        asyncio.run(main("https://e621.net/db_export/", proxy=args.proxy))
    except Exception as e:
        print("A network error occurred:", e)
        print("Try to restart the script with the --proxy argument.")
