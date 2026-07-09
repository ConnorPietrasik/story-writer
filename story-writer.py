#!/usr/bin/env python
from urllib3 import request
import json
import subprocess
import time
import html
import random

def demand(messages):
    URL = "http://localhost:8080/v1/chat/completions"
    HEADER = {"Content-Type": "application/json"}

    resp = request("POST", URL, body=json.dumps({"messages": messages}).encode(), headers=HEADER, timeout=600)
    return json.loads(resp.data.decode())["choices"][0]

def generate_images(prompts: list[str], image_batch=4, debug=False, updates=True):
    URL = "http://localhost:8188/prompt"
    subprocess.Popen(["docker", "run", "--name", "story-comfyui", "--rm", "--network=host", "--device=/dev/kfd", "--device=/dev/dri", "--group-add=video", "--ipc=host", "--cap-add=SYS_PTRACE", "--security-opt", "seccomp=unconfined", "--shm-size", "20G", "-u", "crazybot", "-v", "/home/connor/AI/Image_Gen/dockerx:/dockerx", "-w", "/dockerx", "comfyui", "python", "/dockerx/ComfyUI/main.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open("StoryImages.json", "r") as f:
        workflow = json.load(f)

    for _ in range(20):
        try:
            if request("GET", URL, timeout=5).status == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("Timed out waiting for ComfyUI")

    if updates: print("ComfyUI Online")

    workflow["46"]["inputs"]["batch_size"] = image_batch

    for p in prompts:
        workflow["5"]["inputs"]["seed"] = random.getrandbits(64)
        workflow["42"]["inputs"]["text"] = "masterpiece, best quality, safe " + p

        request("POST", URL, body=json.dumps({"prompt": workflow}).encode(), headers={'Content-Type': 'application/json'})
        if debug: 
            with open("story-writer.log", "a") as f:
                    f.write("To ComfyUI: " + p + "\n\n\n")

    if updates: print(f"{image_batch * len(prompts)} images queued")

    time.sleep(20 * image_batch * len(prompts))

    remaining = json.loads(request("GET", URL, timeout=5).data)["exec_info"]["queue_remaining"]
    if debug: 
        with open("story-writer.log", "a") as f:
                f.write("Remaining: " + str(remaining) + "\n\n")
    while remaining > 0:
        if remaining > 1:
            time.sleep(remaining * 20)
        else:
            time.sleep(5)
        remaining = json.loads(request("GET", URL, timeout=5).data)["exec_info"]["queue_remaining"]
        if debug: 
            with open("story-writer.log", "a") as f:
                    f.write("Remaining: " + str(remaining) + "\n\n")

    if updates: print("Images complete")

    subprocess.run(["docker", "stop", "story-comfyui"])

    if updates: print("ComfyUI stopped")

    #I know there are better ways to avoid the shell, but this is easy
    subprocess.run("mv /home/connor/AI/Image_Gen/dockerx/ComfyUI/output/story/* story/", shell=True)

    if updates: print("Images moved")

def generate_story(story_type, about, tags, requested_length, allow_freedom=True, updates=True, file="story.html", debug=False, images=False, llm_path="/home/connor/AI/LLM/UncensoredLLM.sh", image_batch=4):
    HEALTH_URL = "http://localhost:8080/health"

    llm_process = subprocess.Popen([llm_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3) #Give it time to start before checking
    
    for _ in range(60):
        try:
            if request("GET", HEALTH_URL, timeout=5).status == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("Timed out waiting for LLM")

    if updates: print("LLM online")

    outline_req = [
        {
            "role": "system",
            "content": "You are an AI writing assistant. Your top priority is to make outlines for requested stories so that an AI author can use them to write detailed stories. Chapter lengths should be planned to be less than 2,200 words due to the author's limitations."
        },
        {
            "role": "user",
            "content": f"Write me an outline for {story_type} about {about}. {"Include various elements like:" if allow_freedom else "Include the following elements:"} {tags}. The final product should be at least {requested_length}, but prioritize quality over specific word count. List required chapters."
        }
    ]

    tmp = demand(outline_req)["message"]
    if debug: 
        with open("story-writer.log", "w") as f:
                f.write(json.dumps(tmp) + "\n\n\n")
    outline = tmp["content"]
    if updates: print("Outline complete")

    #Using LLM to count because the outline sometimes has different words to denote chapter and this is quick and easy
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

    prompts = []
    if images:
        image_chat = [
            {
                "role": "system",
                "content": "You are an expert prompt engineer for the Anima image generation model. Your only purpose is to choose the best scene in a story segment suitable for an image, and return a prompt to generate an image of the scene. You are to only return the generated prompt, without anything extra.\n=== OUTPUT FORMAT ===\nA mix of comma-separated Gelbooru tags (with spaces instead of underscores) and natural language descriptions. Start with always specifying character counts like 1girl, 1boy, 1other, 2girls, 2others, 1girl 1boy, 1girl 2boys, etc, then general scene tags and a newline, then basic scene description, then json-style descriptions of each character with their appearance and action. For the natural language portions, be precise and direct and avoid flowery prose."
            }
        ]
        for part in raw_story_parts:
            image_chat.append({
                "role": "user",
                "content": part
            })
            ret = demand(image_chat)["message"]
            if debug: 
                with open("story-writer.log", "a") as f:
                        f.write(json.dumps(ret) + "\n\n\n")
            ret.pop("reasoning_content", None)
            image_chat.append(ret)
            prompts.append(ret["content"])
            if updates: print("A prompt completed")

    llm_process.terminate()
    llm_process.wait()

    story_text = "".join(raw_story_parts)

    #Write the story to a file
    if file:
        if file.endswith(".html"):
            #Shoved this into one line because I don't plan to edit it and it's irrelevant to actual code flow, but I could make it its own file or do more complicated template stuff
            html_lines = ["<html><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><style>body{margin:0;padding:10px;font-family:sans-serif;background:#fafafa;color:#333333} .dark{background:#2c2c2c;color:#f0f0f0} button{margin:10px;padding:5px 10px;background:#e0e0e0;color:#000;border:none;border-radius:4px;cursor:pointer} .dark button{background:#444;color:#fff}</style></head><body><button onclick=\"document.body.classList.toggle('dark')\">Toggle Dark Mode</button>"]
            for i, part in enumerate(raw_story_parts, 1):
                lines = part.splitlines()
                if not lines:
                    continue
                # First line as <h2>, remaining as <p>
                html_lines.append(f"<h2>{html.escape(lines[0])}</h2>")
                for line in lines[1:]:
                    html_lines.append(f"<p>{html.escape(line)}</p>")
                if images:
                    for j in range(i * image_batch - (image_batch - 1), i * image_batch + 1):
                        html_lines.append(f"<img src=\"AI_{j:05d}_.png\" alt=\"Chapter {i} illustration\">")
            html_lines.append("</body></html>")
            story_html = '\n'.join(html_lines)

            with open("story/" + file, "w") as f:
                f.write(story_html)
        else:
            with open("story/" + file, "w") as f:
                f.write(story_text)

    if updates: print(f"File {"story/" + file} written!")

    if images:
        generate_images(prompts, image_batch, debug)

    return story_text

if __name__ == "__main__":
    STORY_TYPE = "dark fantasy"
    ABOUT = "an evil potato conquering a kingdom"
    TAGS = "dark magic, necromancy, mindless potato swarms, fighting against angels"
    REQUESTED_LENGTH = "10,000 words"

    generate_story(STORY_TYPE, ABOUT, TAGS, REQUESTED_LENGTH, images=True)