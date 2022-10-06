# standard imports
import argparse
import json
import os
import pathlib

# lib imports
from dotenv import load_dotenv
import requests
from requests.adapters import HTTPAdapter

# setup environment if running locally
load_dotenv()

# setup requests session
s = requests.Session()
retry_adapter = HTTPAdapter(max_retries=5)
s.mount('https://', retry_adapter)


def save_image_from_url(file_path: str, image_url: str):
    """
    Write image data to file.

    Parameters
    ----------
    file_path : str
        The file path to save the file at. Must include the file extension.
    image_url : str
        The image url.
    """
    # determine the directory
    directory = os.path.dirname(file_path)

    pathlib.Path(directory).mkdir(parents=True, exist_ok=True)

    img_data = s.get(url=image_url).content

    with open(file_path, 'wb') as handler:
        handler.write(img_data)


def write_json_files(file_path: str, data: any):
    """
    Write dictionary to json file.

    Parameters
    ----------
    file_path : str
        The file path to save the file at, excluding the file extension which will be `.json`
    data
        The dictionary data to write in the json file.
    """
    # determine the directory
    directory = os.path.dirname(file_path)

    pathlib.Path(directory).mkdir(parents=True, exist_ok=True)

    with open(f'{file_path}.json', 'w') as f:
        json.dump(obj=data, fp=f, indent=args.indent)


def update_aur():
    """
    Cache and update data from aur API.
    """
    aur_base_url = 'https://aur.archlinux.org/rpc?v=5&type=info&arg='
    aur_repos = ['sunshine']

    for repo in aur_repos:
        url = f'{aur_base_url}{repo}'
        response = s.get(url=url)
        data = response.json()

        file_path = os.path.join('aur', repo)
        write_json_files(file_path=file_path, data=data)


def update_fb():
    """
    Get number of Facebook page likes and group members.
    """
    fb_base_url = 'https://graph.facebook.com/'

    fb_endpoints = dict(
        group=f'{args.facebook_group_id}?fields=member_count,name,description&access_token={args.facebook_token}',
        page=f'{args.facebook_page_id}/insights?metric=page_fans&access_token={args.facebook_token}'
    )

    for key, value in fb_endpoints.items():
        url = f'{fb_base_url}/{value}'
        response = requests.get(url=url)

        data = response.json()

        file_path = os.path.join('facebook', key)
        write_json_files(file_path=file_path, data=data)


def update_github():
    """
    Cache and update GitHub Repo banners.
    """
    response = s.get(url=f'https://api.github.com/users/{args.github_repository_owner}/repos')
    repos = response.json()

    file_path = os.path.join('github', 'repos')
    write_json_files(file_path=file_path, data=repos)

    headers = dict(
        Authorization=f'token {args.github_auth_token}'
    )
    url = 'https://api.github.com/graphql'

    for repo in repos:
        # languages
        response = s.get(url=repo['languages_url'], headers=headers)
        # if TypeError, API limit has likely been exceeded or possible issue with GitHub API...
        # https://www.githubstatus.com/
        # do not error handle, better that workflow fails

        languages = response.json()

        file_path = os.path.join('github', 'languages', repo['name'])
        write_json_files(file_path=file_path, data=languages)

        # openGraphImages
        query = """
        {
          repository(owner: "%s", name: "%s") {
            openGraphImageUrl
          }
        }
        """ % (repo['owner']['login'], repo['name'])

        response = s.post(url=url, json={'query': query}, headers=headers)
        repo_data = response.json()
        try:
            image_url = repo_data['data']['repository']['openGraphImageUrl']
        except KeyError:
            raise SystemExit('"GH_AUTH_TOKEN" is invalid.')
        if 'avatars' not in image_url:
            file_path = os.path.join('github', 'openGraphImages', f"{repo['name']}.png")
            save_image_from_url(file_path=file_path, image_url=image_url)


def readthedocs_loop(url: str, file_path: str) -> list:
    headers = {'Authorization': f'token {args.readthedocs_token}'}

    results = []

    while True:
        response = s.get(url=url, headers=headers)
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            break

        try:
            results.extend(data['results'])
        except KeyError:
            pass

        try:
            url = data['next']
        except KeyError:
            url = None

        if not url:
            break

    if results:
        write_json_files(file_path=file_path, data=results)

    return results


def update_readthedocs():
    """
    Cache and update readthedocs info.
    """
    url_base = 'https://readthedocs.org'
    url = f'{url_base}/api/v3/projects/'

    file_path = os.path.join('readthedocs', 'projects')
    projects = readthedocs_loop(url=url, file_path=file_path)

    for project in projects:
        git_url = project['repository']['url']
        repo_name = git_url.rsplit('/', 1)[-1].rsplit('.git', 1)[0]

        for link in project['_links']:
            file_path = os.path.join('readthedocs', link, repo_name)

            url = project['_links'][link]
            readthedocs_loop(url=url, file_path=file_path)


def missing_arg():
    parser.print_help()
    raise SystemExit()


if __name__ == '__main__':
    # setup arguments using argparse
    parser = argparse.ArgumentParser(description="Update github pages.")
    parser.add_argument('--facebook_group_id', type=str, required=False, default=os.getenv('FACEBOOK_GROUP_ID'),
                        help='Facebook group ID.')
    parser.add_argument('--facebook_page_id', type=str, required=False, default=os.getenv('FACEBOOK_PAGE_ID'),
                        help='Facebook page ID.')
    parser.add_argument('--facebook_token', type=str, required=False, default=os.getenv('FACEBOOK_TOKEN'),
                        help='Facebook Token, requires `groups_access_member_info`, `read_insights`, and '
                             '`pages_read_engagement`. Must be a `page` token, not a `user` token. Token owner must be'
                             'admin of the group.')
    parser.add_argument('--github_repository_owner', type=str, required=False,
                        default=os.getenv('GITHUB_REPOSITORY_OWNER'),
                        help='GitHub Username. Can use environment variable "GITHUB_REPOSITORY_OWNER"')
    parser.add_argument('--github_auth_token', type=str, required=False, default=os.getenv('GH_AUTH_TOKEN'),
                        help='GitHub Token, no scope selection is necessary. Can use environment variable '
                             '"GH_AUTH_TOKEN"')
    parser.add_argument('--readthedocs_token', type=str, required=False, default=os.getenv('READTHEDOCS_TOKEN'),
                        help='Readthedocs API token. Can use environment variable "READTHEDOCS_TOKEN"')
    parser.add_argument('-i', '--indent_json', action='store_true', help='Indent json files.')

    args = parser.parse_args()
    args.indent = 4 if args.indent_json else None

    if not args.facebook_group_id or not args.facebook_page_id or not args.facebook_token \
            or not args.github_repository_owner or not args.github_auth_token or not args.readthedocs_token:
        missing_arg()

    update_aur()
    update_fb()
    update_github()
    update_readthedocs()
