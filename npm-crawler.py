import logging
from json import dump, load
from math import ceil
from time import sleep

import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError
from tqdm import tqdm

package_per_page = 36
dep_selector = "#dependencies > ul:nth-child(2) > li > a"
logging.basicConfig(filename="request.log", level=logging.DEBUG)
s = requests.Session()


def npm_top_dep_format(offset: int):
    return f"https://www.npmjs.com/browse/depended?offset={offset}"


def npm_package_format(package: str):
    return f"https://www.npmjs.com/package/{package}"


def npm_depended_format(module: str, offset: int):
    return f"https://www.npmjs.com/browse/depended/{module}?offset={offset}"


def npm_get_most_depended_upon_packages(limit: int):

    num_pages = ceil(limit / package_per_page)
    packages = []
    for i in range(num_pages):
        url = npm_top_dep_format(i * package_per_page)
        page = requests.get(url)
        soup = BeautifulSoup(page.content, "html.parser")
        deps = soup.find_all(
            "h3",
            class_="db7ee1ac fw6 f4 black-90 dib lh-solid ma0 no-underline hover-black",
        )
        for dep in deps:
            packages.append(dep.text)
    return packages[:limit]


def get_num_dependencies(package: str):
    url = npm_package_format(package)
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "html.parser")
    tags = soup.find_all("span", class_="c3fc8940")
    num_dependents = tags[0].text
    num_dependents = "".join(c for c in num_dependents if c.isdigit())
    return int(num_dependents)


def npm_get_dependents(package: str, num_dependents: int):
    num_pages = ceil(num_dependents / package_per_page)
    packages = []
    for i in range(num_pages):
        url = npm_depended_format(package, i * package_per_page)
        page = requests.get(url)
        soup = BeautifulSoup(page.content, "html.parser")
        deps = soup.find_all(
            "h3",
            class_="db7ee1ac fw6 f4 black-90 dib lh-solid ma0 no-underline hover-black",
        )
        for dep in deps:
            packages.append(dep.text)
        print(f"page {i} finished, result length {len(packages)}")
    return packages


def import_packages_recursive(name, deps_dict, max_depth=10, depth=0):
    if name in deps_dict or depth > max_depth:
        return

    url = npm_package_format(name) + "?activeTab=dependencies"

    try:
        page = requests.get(
            url="https://app.scrapingbee.com/api/v1/",
            params={
                "api_key": "W89DTQW6MCTY0F94F6BYTC7OZ564UQRQV5SUJM75NIUN7WUK69AIUG1H4POV2IO8OBPI159AOES9K4P9",
                "url": url,
                "premium_proxy": "true",
            },
        )
    except ConnectionError:
        logging.debug(name)
        return

    soup = BeautifulSoup(page.content, "html.parser")

    # parse number of dependencies
    tags = soup.find_all("span", class_="c3fc8940")
    if len(tags) == 0:
        logging.debug(name)
        return

    num_dependency = tags[0].text
    num_dependency = "".join(c for c in num_dependency if c.isdigit())
    num_dependency = int(num_dependency)

    # parse dependencies
    dependencies = soup.select(dep_selector)
    dependencies_list = [dep.text for dep in dependencies]

    if num_dependency != len(dependencies_list):
        print(f"request package {name} failed")
        print(num_dependency, len(dependencies_list))

    # print(f'package {name} has dependencies {dependencies_list}')

    deps_dict[name] = dependencies_list

    # recursively call itself to import all dependencies
    for dep in dependencies_list:
        import_packages_recursive(dep, deps_dict, max_depth=max_depth, depth=depth + 1)


def get_repo_url():
    with open("data/wallet_complete_with_failed.json", "r") as file:
        data = load(file)

    url_dict = {}
    for package, _ in tqdm(data.items()):
        url = npm_package_format(package)
        try:
            page = requests.get(
                url="https://app.scrapingbee.com/api/v1/ ",
                params={
                    "api_key": "W89DTQW6MCTY0F94F6BYTC7OZ564UQRQV5SUJM75NIUN7WUK69AIUG1H4POV2IO8OBPI159AOES9K4P9",
                    "url": url,
                    "premium_proxy": "true",
                },
            )
        except ConnectionError:
            logging.debug(package)
            print(f"fetch {package} failed")
            continue

        soup = BeautifulSoup(page.content, "html.parser")
        for tag in soup.find_all(
            "a",
            class_="b2812e30 f2874b88 fw6 mb3 mt2 truncate black-80 f4 link",
            href=True,
        ):
            if "github" in tag["href"]:
                url_dict[package] = tag["href"].replace("#readme", "")
                break
        if package not in url_dict:
            print("failed", package)
    return url_dict


def get_deps():
    with open("data/wallet.json") as file:
        data = load(file)

    counter = 0
    result = {}
    for _, dep_list in data.items():
        for dependency in dep_list:
            import_packages_recursive(dependency, result)
        counter += 1
        print(f"{counter} packages have finished, {len(data)} total.")

    with open(f"data/wallet_complete.json", "w") as file:
        dump(result, file, indent=4)


def fetch_missing_dep():
    failed_package = "@oclif/plugin-help"
    result = {}
    import_packages_recursive(failed_package, result)

    with open("data/wallet_complete.json") as file:
        data = load(file)

    data.update(result)

    with open(f"data/wallet_complete_with_failed.json", "w") as file:
        dump(data, file, indent=4)


def get_urls():
    urls = get_repo_url()
    with open("data/wallet_url.json", "w") as file:
        dump(urls, file, indent=4)


def fetch_missing_url():
    with open("data/wallet_url.json", "r") as file:
        urls = load(file)

    with open("data/wallet_complete_with_failed.json", "r") as file:
        data = load(file)

    try:
        while len(urls) != len(data):
            print(f'{len(urls)}/{len(data)}')
            sleep(5)

            for package, _ in tqdm(data.items()):
                if package in urls:
                    continue

                url = npm_package_format(package)
                try:
                    page = requests.get(url)
                    # page = requests.get(
                    #     url="https://app.scrapingbee.com/api/v1/ ",
                    #     params={
                    #         "api_key": "W89DTQW6MCTY0F94F6 BYTC7OZ564UQRQV5SUJM75NIUN7WUK69AIUG1H4POV2IO8OBPI159AOES9K4P9",
                    #         "url": url,
                    #         "premium_proxy": "true",
                    #     },
                    # )
                except ConnectionError:
                    continue

                soup = BeautifulSoup(page.content, "html.parser")
                for tag in soup.find_all(
                        "a",
                        class_="b2812e30 f2874b88 fw6 mb3 mt2 truncate black-80 f4 link",
                        href=True,
                ):
                    if "github" in tag["href"]:
                        urls[package] = tag["href"].replace("#readme", "")
                        break
    except KeyboardInterrupt:
        with open("data/wallet_url_improved.json", "w") as file:
            dump(urls, file, indent=4)

    with open("data/wallet_url_improved.json", "w") as file:
        dump(urls, file, indent=4)


def clean_urls():
    with open("data/wallet_url.json") as file:
        data = load(file)
    for package, url in data.items():
        data[package] = url.replace("#readme", "")
    with open("data/wallet_url.json", "w") as file:
        dump(data, file, indent=4)


fetch_missing_url()

# # num_package = 100
# # package_list = npm_get_most_depended_upon_packages(num_package)
#
#
# tmp_package = "request"
# num_deps = get_num_dependencies(tmp_package)
# print(num_deps)
# deps_list = npm_get_dependents(tmp_package, num_deps)
# print(deps_list)
# print(len(deps_list))

# result = {}
# import_packages_recursive(tmp_package, result)
# print(result)
