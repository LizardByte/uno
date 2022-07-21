# standard imports
import argparse
import json
import os
import pathlib

# lib imports
import requests
from dotenv import load_dotenv

# setup environment if running locally
load_dotenv()


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

    img_data = requests.get(image_url).content

    with open(file_path, 'wb') as handler:
        handler.write(img_data)


def write_json_files(file_path: str, data: dict):
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
    aur_repos = ['sunshine-git', 'sunshine']

    for repo in aur_repos:
        url = f'{aur_base_url}{repo}'
        response = requests.get(url=url)
        data = response.json()

        file_path = os.path.join('aur', repo)
        write_json_files(file_path=file_path, data=data)


def update_github():
    """
    Cache and update GitHub Repo banners.
    """
    # todo remove token
    response = requests.get(f'https://api.github.com/users/{args.github_repository_owner}/repos')
    repos = response.json()

    file_path = os.path.join('github', 'repos')
    write_json_files(file_path=file_path, data=repos)

    headers = dict(
        Authorization=f'token {args.github_auth_token}'
    )
    url = 'https://api.github.com/graphql'

    for repo in repos:
        # languages
        response = requests.get(repo['languages_url'])
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

        response = requests.post(url=url, json={'query': query}, headers=headers)
        repo_data = response.json()
        image_url = repo_data['data']['repository']['openGraphImageUrl']
        if 'avatars' not in image_url:
            file_path = os.path.join('github', 'openGraphImages', f"{repo['name']}.png")
            save_image_from_url(file_path=file_path, image_url=image_url)


if __name__ == '__main__':
    # setup arguments using argparse
    parser = argparse.ArgumentParser(description="Update github pages.")
    parser.add_argument('--github_repository_owner', type=str, required=False,
                        default=os.getenv('GITHUB_REPOSITORY_OWNER'), help='GitHub Username')
    parser.add_argument('--github_auth_token', type=str, required=False, default=os.getenv('GH_AUTH_TOKEN'),
                        help='GitHub Token, no scope selection is necessary.')
    parser.add_argument('-i', '--indent_json', action='store_true', help='Indent json files.')

    args = parser.parse_args()
    args.indent = 4 if args.indent_json else None

    if not args.github_repository_owner or not args.github_auth_token:
        raise SystemExit('Secrets not supplied. Required environment variables are "GITHUB_REPOSITORY_OWNER", and '
                         '"GH_AUTH_TOKEN". They should be placed in org/repo secrets and passed in as arguments if '
                         'using github, or ".env" file if running local.')

    update_aur()
    update_github()
