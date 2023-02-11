"""
e621 tagger companion - database downloader

Author: AyoKeito
Version: 1.0.0
GitHub: https://github.com/johndoe/my-python-script

To tag stuff, you should know stuff.
"""

import re
import asyncio
import aiohttp
import gzip
import pandas as pd
import argparse
import io
import faulthandler

parser = argparse.ArgumentParser(description="Download and process CSV files. Download gz archives, extract & filter irrelevant data, and save as compressed parquet files.")
parser.add_argument("--proxy", help="The proxy to use for all network calls (optional). Usage examples: http://proxy.server:8888 or http://user:password@proxy.server:8888")
args = parser.parse_args()

async def download_file(session, url):
    async with session.get(url, headers={'User-Agent': 'e621 tagger'}, proxy=args.proxy) as resp:
        if resp.status == 200:
            content = await resp.content.read()
            return content

async def main(url, proxy):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={'User-Agent': 'e621 tagger'}, proxy=args.proxy) as resp:
            if resp.status == 200:
                faulthandler.enable()
                print(f"Step 1: Got response from {url}")
                content = await resp.text()
                file_links = re.findall(r'<a href="(.*?)">', content)
                latest_posts = sorted([x for x in file_links if x.startswith("posts")], reverse=True)[0]
                try:
                    print(f"Step 2: Downloading {latest_posts}")
                    posts_content = gzip.decompress(await download_file(session, url + latest_posts))

                    print(f"Step 3: Reading {latest_posts} as a DataFrame")
                    posts_df = pd.read_csv(io.BytesIO(posts_content), usecols=["id", "md5", "tag_string"])

                    print(f"Step 4: Saving DataFrame to posts.parquet")
                    posts_df.to_parquet("posts.parquet", engine='pyarrow', compression='brotli')

                    print(f"\033[32mStep 5: posts.parquet done!\033[0m")
                    del posts_df
                except Exception as e:
                    print("An error occurred while downloading the latest posts:", e)
                    return

                content = await resp.text()
                file_links = re.findall(r'<a href="(.*?)">', content)
                latest_tags = sorted([x for x in file_links if x.startswith("tags")], reverse=True)[0]
                try:
                    print(f"Step 6: Downloading latest tags file {latest_tags}")
                    tags_content = gzip.decompress(await download_file(session, url + latest_tags)).decode()
					
                    print(f"Step 7: Reading {latest_tags} as a DataFrame")
                    df = pd.read_csv(io.BytesIO(bytes(tags_content, "utf-8")), header=0, dtype={"id": int, "name": str, "category": int, "post_count": int})
					
                    print(f"Step 8: Filtering DataFrame to only include rows where category is equal to 1 (artists)")
                    df = df[df["category"] == 1]
					
                    print(f"Step 9: Keeping only the 'name' column from the DataFrame")
                    df = df[["name"]]
					
                    print(f"Step 10: Saving DataFrame to artists.parquet")
                    df.to_parquet("artists.parquet", engine='pyarrow', compression='snappy')
					
                    print(f"\033[32mStep 11: artists.parquet done!\033[0m")
                    del df
                except Exception as e:
                    print("An error occurred while downloading the latest tags:", e)
                    return

try:
    asyncio.run(main("https://e621.net/db_export/", proxy=args.proxy))
except Exception as e:
    print("A network error occurred:", e)
    print("Try to restart the script with the --proxy argument.")
