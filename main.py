#!/usr/bin/env python

import srt
import argparse
from openai import AzureOpenAI
import json
import os
from dotenv import load_dotenv
from time import sleep

load_dotenv()  # take environment variables from .env.


BATCHSIZE = 50  # later i may use a token conter instead but this is simpler for now
LANG = "french"
MODEL = "gpt-3.5-turbo"
VERBOSE = False


def getClient(azure_endpoint, api_key, api_version="2024-02-15-preview"):
    return AzureOpenAI(
        azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
        api_key=os.getenv("OPENAI_API_KEY"),
        api_version="2024-02-15-preview",
    )


def makeprompt():
    global prompt
    prompt = f"""You are a professional translator.
Translate the text below line by line into {LANG}, do not add any content on your own, and aside from translating, do not produce any other text, you will make the most accurate and authentic to the source translation possible.

these are subtitles, meaning each elements are related and in order, you can use this context to make a better translation.
you will reply with a json array that only contain the translation."""


def makebatch(chunk):
    return [x.content for x in chunk]


def translate_batch(client, batch, maxretry=5):
    blen = len(batch)
    tbatch = []
    batch = json.dumps(batch, ensure_ascii=False)
    lendiff = 1
    while lendiff != 0 and maxretry > 0:  # TODO add max retry ?
        try:
            print(batch)
            completion = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": batch},
                ],
            )
            tbatch = json.loads(completion.choices[0].message.content)
            print(tbatch)
        except Exception as e:
            if VERBOSE:
                print(e)
            lendiff = 1
            maxretry -= 1
        else:
            lendiff = len(tbatch) - blen
    return tbatch


def translate_file(client, subs, maxretry=5):
    total_batch = (len(subs) + BATCHSIZE - 1) // BATCHSIZE
    for i in range(0, len(subs), BATCHSIZE):
        print(f"batch {i//BATCHSIZE + 1} / {total_batch}")

        chunk = subs[i : i + BATCHSIZE]
        batch = makebatch(chunk)
        batch = translate_batch(client, batch, maxretry)
        if len(batch) != len(chunk):
            for j in range(len(chunk)):
                ret = translate_batch(client, [chunk[j].content], maxretry)
                if len(ret) > 0:
                    chunk[j].content = ret[0]
        else:
            for j, n in enumerate(batch):
                chunk[j].content = n


def get_translated_filename(filepath):
    root, ext = os.path.splitext(os.path.basename(filepath))
    return f"{root}_{LANG}{ext}"


def main():
    parser = argparse.ArgumentParser(description="Translate srt files")
    parser.add_argument("files", help="File pattern to match", nargs="+")
    parser.add_argument(
        "-l", "--language", help="Specify the language", default="french", type=str
    )
    parser.add_argument(
        "-b", "--batch_size", help="Specify the batch size", default=50, type=int
    )
    parser.add_argument(
        "-m", "--model", help="openai's model to use", default="gpt-3.5-turbo", type=str
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="display errors and debug infomration",
        action="store_true",
    )
    parser.add_argument(
        "-a",
        "--api_version",
        help="Azure OpenAI version",
        default="2024-02-15-preview",
        type=str,
    )
    parser.add_argument(
        "--max_retry", help="max retry for a batch", default=5, type=int
    )
    args = parser.parse_args()

    files = args.files
    azure_endpoint = os.getenv("OPENAI_ENDPOINT")
    api_key = os.getenv("OPENAI_API_KEY")
    if not azure_endpoint or not api_key:
        print("Please set OPENAI_ENDPOINT and OPENAI_API_KEY in your environment.")
        return
    client = getClient(azure_endpoint, api_key, args.api_version)
    global LANG, BATCHSIZE, MODEL, VERBOSE
    LANG = args.language
    BATCHSIZE = args.batch_size
    MODEL = args.model
    VERBOSE = args.verbose
    makeprompt()

    if not files:
        print("No files found matching the pattern.")
        return

    for filename in files:
        print(filename)
        sub = open(filename).read()
        subs = list(srt.parse(sub))

        # batch = makebatch(subs[10:15])
        # print(batch)
        # tbatch = translate_batch(batch)
        # print(tbatch)

        translate_file(client, subs)
        output = srt.compose(subs)

        with open(get_translated_filename(filename), "w") as handle:
            handle.write(output)


if __name__ == "__main__":
    main()
