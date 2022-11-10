#!/usr/bin/env python3
#
# natbot.py
#
# Set OPENAI_API_KEY to your API key, and then run this from a terminal.
#


import os
import time
from sys import argv, exit

import openai

from crawler import Crawler

quiet = False
if len(argv) >= 2:
    if argv[1] == '-q' or argv[1] == '--quiet':
        quiet = True
        print(
            "Running in quiet mode (HTML and other content hidden); \n"
            + "exercise caution when running suggested commands."
        )

prompt_template = """
You are an agent controlling a browser. You are given:

	(1) an objective that you are trying to achieve
	(2) the URL of your current web page
	(3) a simplified text description of what's visible in the browser window (more on that below)

You can issue these commands:
	SCROLL UP - scroll up one page
	SCROLL DOWN - scroll down one page
	CLICK X - click on a given element. You can only click on links, buttons, and inputs!
	TYPE X "TEXT" - type the specified text into the input with id X
	TYPESUBMIT X "TEXT" - same as TYPE above, except then it presses ENTER to submit the form

The format of the browser content is highly simplified; all formatting elements are stripped.
Interactive elements such as links, inputs, buttons are represented like this:

		<link id=1>text</link>
		<button id=2>text</button>
		<input id=3>text</input>

Images are rendered as their alt text like this:

		<img id=4 alt=""/>

Based on your given objective, issue whatever command you believe will get you closest to achieving your goal.
You always start on Google; you should submit a search query to Google that will take you to the best page for
achieving your objective. And then interact with that page to achieve your objective.

If you find yourself on Google and there are no search results displayed yet, you should probably issue a command 
like "TYPESUBMIT 7 "search query"" to get to a more useful page.

Then, if you find yourself on a Google search results page, you might issue the command "CLICK 24" to click
on the first link in the search results. (If your previous command was a TYPESUBMIT your next command should
probably be a CLICK.)

Don't try to interact with elements that you can't see.

Here are some examples:

EXAMPLE 1:
==================================================
CURRENT BROWSER CONTENT:
------------------
<link id=1>About</link>
<link id=2>Store</link>
<link id=3>Gmail</link>
<link id=4>Images</link>
<link id=5>(Google apps)</link>
<link id=6>Sign in</link>
<img id=7 alt="(Google)"/>
<input id=8 alt="Search"></input>
<button id=9>(Search by voice)</button>
<button id=10>(Google Search)</button>
<button id=11>(I'm Feeling Lucky)</button>
<link id=12>Advertising</link>
<link id=13>Business</link>
<link id=14>How Search works</link>
<link id=15>Carbon neutral since 2007</link>
<link id=16>Privacy</link>
<link id=17>Terms</link>
<text id=18>Settings</text>
------------------
OBJECTIVE: Find a 2 bedroom house for sale in Anchorage AK for under $750k
CURRENT URL: https://www.google.com/
YOUR COMMAND: 
TYPESUBMIT 8 "anchorage redfin"
==================================================

EXAMPLE 2:
==================================================
CURRENT BROWSER CONTENT:
------------------
<link id=1>About</link>
<link id=2>Store</link>
<link id=3>Gmail</link>
<link id=4>Images</link>
<link id=5>(Google apps)</link>
<link id=6>Sign in</link>
<img id=7 alt="(Google)"/>
<input id=8 alt="Search"></input>
<button id=9>(Search by voice)</button>
<button id=10>(Google Search)</button>
<button id=11>(I'm Feeling Lucky)</button>
<link id=12>Advertising</link>
<link id=13>Business</link>
<link id=14>How Search works</link>
<link id=15>Carbon neutral since 2007</link>
<link id=16>Privacy</link>
<link id=17>Terms</link>
<text id=18>Settings</text>
------------------
OBJECTIVE: Make a reservation for 4 at Dorsia at 8pm
CURRENT URL: https://www.google.com/
YOUR COMMAND: 
TYPESUBMIT 8 "dorsia nyc opentable"
==================================================

EXAMPLE 3:
==================================================
CURRENT BROWSER CONTENT:
------------------
<button id=1>For Businesses</button>
<button id=2>Mobile</button>
<button id=3>Help</button>
<button id=4 alt="Language Picker">EN</button>
<link id=5>OpenTable logo</link>
<button id=6 alt ="search">Search</button>
<text id=7>Find your table for any occasion</text>
<button id=8>(Date selector)</button>
<text id=9>Sep 28, 2022</text>
<text id=10>7:00 PM</text>
<text id=11>2 people</text>
<input id=12 alt="Location, Restaurant, or Cuisine"></input> 
<button id=13>Let’s go</button>
<text id=14>It looks like you're in Peninsula. Not correct?</text> 
<button id=15>Get current location</button>
<button id=16>Next</button>
------------------
OBJECTIVE: Make a reservation for 4 for dinner at Dorsia in New York City at 8pm
CURRENT URL: https://www.opentable.com/
YOUR COMMAND: 
TYPESUBMIT 12 "dorsia new york city"
==================================================

The current browser content, objective, and current URL follow. Reply with your next command to the browser.

CURRENT BROWSER CONTENT:
------------------
$browser_content
------------------

OBJECTIVE: $objective
CURRENT URL: $url
PREVIOUS COMMAND: $previous_command
YOUR COMMAND:
"""

if (
        __name__ == "__main__"
):
    _crawler = Crawler()
    openai.api_key = os.environ.get("OPENAI_API_KEY")


    def print_help():
        print(
            "(g) to visit url\n(u) scroll up\n(d) scroll down\n(c) to click\n(t) to type\n" +
            "(h) to view commands again\n(r/enter) to run suggested command\n(o) change objective"
        )

    def get_gpt_command(objective, url, previous_command, browser_content):
        prompt = prompt_template
        prompt = prompt.replace("$objective", objective)
        prompt = prompt.replace("$url", url[:100])
        prompt = prompt.replace("$previous_command", previous_command)
        prompt = prompt.replace("$browser_content", browser_content[:4500])
        response = openai.Completion.create(model="text-davinci-002", prompt=prompt, temperature=0.5, best_of=10, n=3,
                                            max_tokens=50)
        return response.choices[0].text


    def run_cmd(cmd):
        cmd = cmd.split("\n")[0]

        if cmd.startswith("SCROLL UP"):
            _crawler.scroll("up")
        elif cmd.startswith("SCROLL DOWN"):
            _crawler.scroll("down")
        elif cmd.startswith("CLICK"):
            commasplit = cmd.split(",")
            id = commasplit[0].split(" ")[1]
            _crawler.click(id)
        elif cmd.startswith("TYPE"):
            spacesplit = cmd.split(" ")
            id = spacesplit[1]
            text = spacesplit[2:]
            text = " ".join(text)
            # Strip leading and trailing double quotes
            text = text[1:-1]

            if cmd.startswith("TYPESUBMIT"):
                text += '\n'
            _crawler.type(id, text)

        time.sleep(2)


    objective = "Make a reservation for 2 at 7pm at bistro vida in menlo park"
    print("\nWelcome to natbot! What is your objective?")
    i = input()
    if len(i) > 0:
        objective = i

    gpt_cmd = ""
    prev_cmd = ""
    _crawler.go_to_page("google.com")
    try:
        while True:
            browser_content = "\n".join(_crawler.crawl())
            prev_cmd = gpt_cmd
            gpt_cmd = get_gpt_command(objective, _crawler.page.url, prev_cmd, browser_content)
            gpt_cmd = gpt_cmd.strip()

            if not quiet:
                print("URL: " + _crawler.page.url)
                print("Objective: " + objective)
                print("----------------\n" + browser_content + "\n----------------\n")
            if len(gpt_cmd) > 0:
                print("Suggested command: " + gpt_cmd)

            command = input()
            if command == "r" or command == "":
                run_cmd(gpt_cmd)
            elif command == "g":
                url = input("URL:")
                _crawler.go_to_page(url)
            elif command == "u":
                _crawler.scroll("up")
                time.sleep(1)
            elif command == "d":
                _crawler.scroll("down")
                time.sleep(1)
            elif command == "c":
                id = input("id:")
                _crawler.click(id)
                time.sleep(1)
            elif command == "t":
                id = input("id:")
                text = input("text:")
                _crawler.type(id, text)
                time.sleep(1)
            elif command == "o":
                objective = input("Objective:")
            else:
                print_help()
    except KeyboardInterrupt:
        print("\n[!] Ctrl+C detected, exiting gracefully.")
        exit(0)
