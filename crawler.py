import time
from sys import platform

from playwright.sync_api import sync_playwright

black_listed_elements = {"html", "head", "title", "meta", "iframe", "body", "script", "style", "path", "svg", "br",
                         "::marker"}


def convert_name(node_name, has_click_handler):
    if node_name == "a":
        return "link"
    if node_name == "input":
        return "input"
    if node_name == "img":
        return "img"
    if (
            node_name == "button" or has_click_handler
    ):  # found pages that needed this quirk
        return "button"
    else:
        return "text"


def find_attributes(attributes, keys, strings):
    values = {}

    for [key_index, value_index] in zip(*(iter(attributes),) * 2):
        if value_index < 0:
            continue
        key = strings[key_index]
        value = strings[value_index]

        if key in keys:
            values[key] = value
            keys.remove(key)

            if not keys:
                return values

    return values


def add_to_hash_tree(hash_tree, tag, node_id, node_name, parent_id, strings, parent, node_names):
    parent_id_str = str(parent_id)
    if not parent_id_str in hash_tree:
        parent_name = strings[node_names[parent_id]].lower()
        grand_parent_id = parent[parent_id]

        add_to_hash_tree(
            hash_tree, tag, parent_id, parent_name, grand_parent_id
        )

    is_parent_desc_anchor, anchor_id = hash_tree[parent_id_str]

    # even if the anchor is nested in another anchor, we set the "root" for all descendants to be ::Self
    if node_name == tag:
        value = (True, node_id)
    elif (
            is_parent_desc_anchor
    ):  # reuse the parent's anchor_id (which could be much higher in the tree)
        value = (True, anchor_id)
    else:
        value = (
            False,
            None,
        )  # not a descendant of an anchor, most likely it will become text, an interactive element or discarded

    hash_tree[str(node_id)] = value

    return value


class Crawler:
    def __init__(self):
        self.browser = (
            sync_playwright()
            .start()
            .chromium.launch(
                headless=False,
            )
        )

        self.page = self.browser.new_page()
        self.page.set_viewport_size({"width": 1280, "height": 1080})

    def go_to_page(self, url):
        self.page.goto(url=url if "://" in url else "http://" + url)
        self.client = self.page.context.new_cdp_session(self.page)
        self.page_element_buffer = {}

    def scroll(self, direction):
        if direction == "up":
            self.page.evaluate(
                "(document.scrollingElement || document.body).scrollTop = (document.scrollingElement || document.body).scrollTop - window.innerHeight;"
            )
        elif direction == "down":
            self.page.evaluate(
                "(document.scrollingElement || document.body).scrollTop = (document.scrollingElement || document.body).scrollTop + window.innerHeight;"
            )

    def click(self, id):
        # Inject javascript into the page which removes the target= attribute from all links
        js = """
		links = document.getElementsByTagName("a");
		for (var i = 0; i < links.length; i++) {
			links[i].removeAttribute("target");
		}
		"""
        self.page.evaluate(js)

        element = self.page_element_buffer.get(int(id))
        if element:
            x = element.get("center_x")
            y = element.get("center_y")

            self.page.mouse.click(x, y)
        else:
            print("Could not find element")

    def type(self, id, text):
        self.click(id)
        self.page.keyboard.type(text)

    def enter(self):
        self.page.keyboard.press("Enter")

    def crawl(self):
        page = self.page
        page_element_buffer = self.page_element_buffer
        start = time.time()

        page_state_as_text = []

        device_pixel_ratio = page.evaluate("window.devicePixelRatio")
        if platform == "darwin" and device_pixel_ratio == 1:  # lies
            device_pixel_ratio = 2

        win_upper_bound = page.evaluate("window.pageYOffset")
        win_left_bound = page.evaluate("window.pageXOffset")
        win_width = page.evaluate("window.screen.width")
        win_height = page.evaluate("window.screen.height")
        win_right_bound = win_left_bound + win_width
        win_lower_bound = win_upper_bound + win_height

        percentage_progress_start = 1
        percentage_progress_end = 2

        page_state_as_text.append(
            {
                "x": 0,
                "y": 0,
                "text": "[scrollbar {:0.2f}-{:0.2f}%]".format(
                    round(percentage_progress_start, 2), round(percentage_progress_end)
                ),
            }
        )

        tree = self.client.send(
            "DOMSnapshot.captureSnapshot",
            {"computedStyles": [], "includeDOMRects": True, "includePaintOrder": True},
        )
        strings = tree["strings"]
        document = tree["documents"][0]
        nodes = document["nodes"]
        backend_node_id = nodes["backendNodeId"]
        attributes = nodes["attributes"]
        node_value = nodes["nodeValue"]
        parent = nodes["parentIndex"]
        node_types = nodes["nodeType"]
        node_names = nodes["nodeName"]
        is_clickable = set(nodes["isClickable"]["index"])

        text_value = nodes["textValue"]
        text_value_index = text_value["index"]
        text_value_values = text_value["value"]

        input_value = nodes["inputValue"]
        input_value_index = input_value["index"]
        input_value_values = input_value["value"]

        input_checked = nodes["inputChecked"]
        layout = document["layout"]
        layout_node_index = layout["nodeIndex"]
        bounds = layout["bounds"]

        cursor = 0
        html_elements_text = []

        child_nodes = {}
        elements_in_view_port = []

        anchor_ancestry = {"-1": (False, None)}
        button_ancestry = {"-1": (False, None)}

        for index, node_name_index in enumerate(node_names):
            node_parent = parent[index]
            node_name = strings[node_name_index].lower()

            is_ancestor_of_anchor, anchor_id = add_to_hash_tree(
                anchor_ancestry, "a", index, node_name, node_parent, strings, parent, node_names
            )

            is_ancestor_of_button, button_id = add_to_hash_tree(
                button_ancestry, "button", index, node_name, node_parent, strings, parent, node_names
            )

            try:
                cursor = layout_node_index.index(
                    index
                )  # todo replace this with proper cursoring, ignoring the fact this is O(n^2) for the moment
            except:
                continue

            if node_name in black_listed_elements:
                continue

            [x, y, width, height] = bounds[cursor]
            x /= device_pixel_ratio
            y /= device_pixel_ratio
            width /= device_pixel_ratio
            height /= device_pixel_ratio

            elem_left_bound = x
            elem_top_bound = y
            elem_right_bound = x + width
            elem_lower_bound = y + height

            partially_is_in_viewport = (
                    elem_left_bound < win_right_bound
                    and elem_right_bound >= win_left_bound
                    and elem_top_bound < win_lower_bound
                    and elem_lower_bound >= win_upper_bound
            )

            if not partially_is_in_viewport:
                continue

            meta_data = []

            # inefficient to grab the same set of keys for kinds of objects, but it's fine for now
            element_attributes = find_attributes(
                attributes[index], ["type", "placeholder", "aria-label", "title", "alt"], strings
            )

            ancestor_exception = is_ancestor_of_anchor or is_ancestor_of_button
            ancestor_node_key = (
                None
                if not ancestor_exception
                else str(anchor_id)
                if is_ancestor_of_anchor
                else str(button_id)
            )
            ancestor_node = (
                None
                if not ancestor_exception
                else child_nodes.setdefault(str(ancestor_node_key), [])
            )

            if node_name == "#text" and ancestor_exception:
                text = strings[node_value[index]]
                if text == "|" or text == "•":
                    continue
                ancestor_node.append({
                    "type": "type", "value": text
                })
            else:
                if (
                        node_name == "input" and element_attributes.get("type") == "submit"
                ) or node_name == "button":
                    node_name = "button"
                    element_attributes.pop(
                        "type", None
                    )  # prevent [button ... (button)..]

                for key in element_attributes:
                    if ancestor_exception:
                        ancestor_node.append({
                            "type": "attribute",
                            "key": key,
                            "value": element_attributes[key]
                        })
                    else:
                        meta_data.append(element_attributes[key])

            element_node_value = None

            if node_value[index] >= 0:
                element_node_value = strings[node_value[index]]
                if element_node_value == "|":  # commonly used as a seperator, does not add much context - lets save ourselves some token space
                    continue
            elif (
                    node_name == "input"
                    and index in input_value_index
                    and element_node_value is None
            ):
                node_input_text_index = input_value_index.index(index)
                text_index = input_value_values[node_input_text_index]
                if node_input_text_index >= 0 and text_index >= 0:
                    element_node_value = strings[text_index]

            # remove redudant elements
            if ancestor_exception and (node_name != "a" and node_name != "button"):
                continue

            elements_in_view_port.append(
                {
                    "node_index": str(index),
                    "backend_node_id": backend_node_id[index],
                    "node_name": node_name,
                    "node_value": element_node_value,
                    "node_meta": meta_data,
                    "is_clickable": index in is_clickable,
                    "origin_x": int(x),
                    "origin_y": int(y),
                    "center_x": int(x + (width / 2)),
                    "center_y": int(y + (height / 2)),
                }
            )

        # lets filter further to remove anything that does not hold any text nor has click handlers + merge text from leaf#text nodes with the parent
        elements_of_interest = []
        id_counter = 0

        for element in elements_in_view_port:
            node_index = element.get("node_index")
            node_name = element.get("node_name")
            node_value = element.get("node_value")
            is_clickable = element.get("is_clickable")
            origin_x = element.get("origin_x")
            origin_y = element.get("origin_y")
            center_x = element.get("center_x")
            center_y = element.get("center_y")
            meta_data = element.get("node_meta")

            inner_text = f"{node_value} " if node_value else ""
            meta = ""

            if node_index in child_nodes:
                for child in child_nodes.get(node_index):
                    entry_type = child.get('type')
                    entry_value = child.get('value')

                    if entry_type == "attribute":
                        entry_key = child.get('key')
                        meta_data.append(f'{entry_key}="{entry_value}"')
                    else:
                        inner_text += f"{entry_value} "

            if meta_data:
                meta_string = " ".join(meta_data)
                meta = f" {meta_string}"

            if inner_text != "":
                inner_text = f"{inner_text.strip()}"

            converted_node_name = convert_name(node_name, is_clickable)

            # not very elegant, more like a placeholder
            if (
                    (converted_node_name != "button" or meta == "")
                    and converted_node_name != "link"
                    and converted_node_name != "input"
                    and converted_node_name != "img"
                    and converted_node_name != "textarea"
            ) and inner_text.strip() == "":
                continue

            page_element_buffer[id_counter] = element

            if inner_text != "":
                elements_of_interest.append(
                    f"""<{converted_node_name} id={id_counter}{meta}>{inner_text}</{converted_node_name}>"""
                )
            else:
                elements_of_interest.append(
                    f"""<{converted_node_name} id={id_counter}{meta}/>"""
                )
            id_counter += 1

        print("Parsing time: {:0.2f} seconds".format(time.time() - start))
        return elements_of_interest