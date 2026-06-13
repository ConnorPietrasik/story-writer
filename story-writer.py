#!/usr/bin/env python
from urllib3 import request
import json

def demand(messages):
    URL = "http://localhost:8080/v1/chat/completions"
    HEADER = {"Content-Type": "application/json"}

    resp = request("POST", URL, body=json.dumps({"messages": messages}).encode(), headers=HEADER, timeout=600)
    return json.loads(resp.data.decode())["choices"][0]

def generate_story(story_type, about, tags, requested_length, allow_freedom=True, updates=True, file="story.html", debug=False, images=False):
    """
    Generate a story using the LLM based on the given parameters.
    Returns the story as a string.
    """

    outline_req = [
        {
            "role": "system",
            "content": "You are an AI writing assistant. Your top priority is to make outlines for requested stories so that an AI author can use them to write detailed stories."
        },
        {
            "role": "user",
            "content": f"Write me an outline for {story_type} about {about}. Include the following elements: {tags}.{"Feel free to add other elements as fitting." if allow_freedom else ""} The final product should be around {requested_length}. List required chapters."
        }
    ]

    tmp = demand(outline_req)["message"]
    if debug: 
        with open("story-writer.log", "w") as f:
                f.write(json.dumps(tmp) + "\n\n\n")
    outline = tmp["content"]
    if updates: print("Outline complete")

    # Using LLM to count because the outline sometimes has different words to denote chapter and this is quick and easy
    count_req = [
        {
            "role": "system",
            "content": "You are an AI writing assistant. Your only purpose is to determine how many chapters the given outline requires when fully written and return just the number, without anything else. Any listed prologue or epilogue should be included in the count."
        },
        {
            "role": "user",
            "content": outline
        }
    ]

    tmp = demand(count_req)["message"]
    if debug: 
        with open("story-writer.log", "a") as f:
                f.write(json.dumps(tmp) + "\n\n\n")
    chapter_count = int(tmp["content"])
    if updates: print(f"Total chapters: {chapter_count}")

    chapter_chat = [
        {
            "role": "system",
            "content": f"You are an author dedicated to {story_type}. Your purpose is to write a story based on the following outline, while avoiding repetitive phrasing: {outline}"
        },
        {
            "role": "user",
            "content": "Write the first chapter."
        }
    ]

    for i in range(chapter_count):
        ret = demand(chapter_chat)["message"]
        if debug: 
            with open("story-writer.log", "a") as f:
                    f.write(json.dumps(ret) + "\n\n\n")
        ret.pop("reasoning_content", None)
        chapter_chat.append(ret)
        chapter_chat.append({
            "role": "user",
            "content": "Write the next chapter."
        })
        if updates: print(f"Chapter {i + 1} complete")

    raw_story_parts = [x["content"] for x in chapter_chat if x["role"] == "assistant"]

    if images:
        image_chat = [
            {
                "role": "system",
                "content": "You are an expert prompt engineer for the Anima image generation model. Your only purpose is to determine the best scene in a story segment and return a prompt suitable for generating an image of the scene. You are to only return the generated prompt, without anything extra.\n=== OUTPUT FORMAT ===\nA mix of Gelbooru tags (with spaces instead of underscores) and natural language descriptions. Start with always specifying character counts like 1girl, 1boy, 1other, 2girls, 2others, 1girl 1boy, 1girl 2boys, etc, then general scene tags + description, then more detailed tags and descriptions per character."
            }
        ]
        for part in raw_story_parts:
            image_chat.append({
                "role": "user",
                "content": part
            })
            prompts = []
            ret = demand(image_chat)["message"]
            if debug: 
                with open("story-writer.log", "a") as f:
                        f.write(json.dumps(ret) + "\n\n\n")
            ret.pop("reasoning_content", None)
            image_chat.append(ret)
            prompts.append(ret["content"])

        #TODO Actually generate images here

    story_text = "".join(raw_story_parts)

    # Write the story to a file
    if file:
        if file.endswith(".html"):
            #Shoved this into one line because I don't plan to edit it and it's irrelevant to actual code flow, but I could make it its own file or do more complicated template stuff
            html_lines = ["<html><head><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><style>body{margin:0;padding:10px;font-family:sans-serif;background:#fafafa;color:#333333} .dark{background:#2c2c2c;color:#f0f0f0} button{margin:10px;padding:5px 10px;background:#e0e0e0;color:#000;border:none;border-radius:4px;cursor:pointer} .dark button{background:#444;color:#fff}</style></head><body><button onclick=\"document.body.classList.toggle('dark')\">Toggle Dark Mode</button>"]
            for i, part in enumerate(raw_story_parts, 1):
                lines = part.splitlines()
                if not lines:
                    continue
                # First line as <h2>, remaining as <p>
                html_lines.append(f"<h2>{lines[0]}</h2>")
                for line in lines[1:]:
                    html_lines.append(f"<p>{line}</p>")
                if images:
                    html_lines.append(f"<img src=\"AI_{i:05d}_.png\" alt=\"Chapter {i} illustration\">")
            html_lines.append("</body></html>")
            story_html = '\n'.join(html_lines)

            with open(file, "w") as f:
                f.write(story_html)
        else:
            with open(file, "w") as f:
                f.write(story_text)

    if updates: print(f"File {file} written!")

    return story_text

if __name__ == "__main__":
    STORY_TYPE = "dark fantasy"
    ABOUT = "a magical potato conquering a kingdom"
    TAGS = "dark magic, necromancy, eating disobedient mortals, potato minions"
    REQUESTED_LENGTH = "10,000 words"

    print(generate_story(STORY_TYPE, ABOUT, TAGS, REQUESTED_LENGTH, debug=True, images=True))
