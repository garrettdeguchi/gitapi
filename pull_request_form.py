import requests
import pandas as pd
import sys, getopt, os
import configparser
import logging
from enum import Enum
import ast

from pprint import pprint

github_url = 'https://api.github.com'

vyaire_repos_base = 'https://api.github.com/repos/vyaire/' # Add repository
vyaire_pull_req_base = 'https://api.github.com/repos/vyaire/fabian-gui/pulls?state=closed&per_page=' # Add number


# Configuring the logger this will be used as a global over the whole program
LOG_FORMAT = "%(levelname)s %(asctime)s - %(message)s"
logging.basicConfig(filename="pull_request_form.log", level=logging.DEBUG, format=LOG_FORMAT, filemode='w')
logger = logging.getLogger()


authentication = [None, None]


class Indexing(Enum):
    USERNAME = 0
    PASSWORD = 1
    CONFIG_COMMIT_START = 0
    CONFIG_COMMIT_END = 1
    CLASS_REPO_NAME = 0
    CLASS_COMMIT_START = 1
    CLASS_COMMIT_END = 2
    CLASS_REPO_BRANCH = 3


class Repositories(Enum):
    # Repository, Start commit, End commit
    fabian_gui = ['fabian-gui', None, None, 'master']
    fabian_monitor = ['fabian-monitor', None, None, 'master']
    fabian_controller = ['fabian-controller', None, None, 'master']
    fabian_alarm = ['fabian-alarm', None, None, 'master']
    fabian_blender = ['fabian-blender', None, None, 'master']
    fabian_power = ['fabian-power', None, None, 'master']
    fabian_power_evo = ['fabian-power-evo', None, None, 'master']
    fabian_hfo = ['fabian-hfo', None, None, 'master']
    fabian_controller_bootloader = ['fabian-controller_bootloader', None, None, 'master']
    fabian_alarm_bootloader = ['fabian-alarm_bootloader', None, None, 'master']
    fabian_monitor_bootloader = ['fabian-monitor_bootloader', None, None, 'master']
    fabian_hfo_bootloader = ['fabian-hfo_bootloader', None, None, 'master']


class Columns(Enum):
    df_files = 'files'
    df_filenames = 'filename'
    df_users = 'user'


class PRItems(Enum):
    number = 'number'
    url = 'url'
    title = 'title'
    user = 'user'
    merged_at = 'merged_at'
    merged_commit_sha = 'merge_commit_sha'
    parents = 'parents'
    sha = 'sha'
    base = 'base'
    ref = 'ref'


class PRIndexesBefore(Enum):
    index = 0
    commit_title = 1
    commit_sha_parent = 2
    files_changed = 3
    commit_sha = 4


class PRIndexesAfter(Enum):
    index = 0
    commit_sha = 1
    commit_title = 2
    commit_parent = 3
    files_changed = 4
    pr_num = 5
    url = 6
    submitter = 7
    date = 8
    reviewers = 9
    total_title = 10


class QueryItems(Enum):
    pull_state_closed = '/pulls?state=closed&per_page=400'
    pulls = '/pulls/'
    commits = "/commits/"
    commit_break = " || "


class FormHeader(Enum):
    pr_num = 'PR #'
    submitter = 'Submitter'
    merged_date = 'Merged Date'
    title = 'Title'
    reviewers = 'Reviewers'
    files = 'Files'
    commits = 'Commits'


class MiscValues(Enum):
    COMMIT_LENGTH = 40
    COMMIT_BREAK_SIZE = len(QueryItems.commit_break.value)
    PR_ITEM_LENGTH = 11


class PullRequestForm:

    def __init__(self):
        pd.set_option("display.max_columns", 500)
        pd.set_option("display.max_rows", 500)
        pd.set_option("display.max_colwidth", 500)

    def generate_form(self, auth_info):
        for repo in Repositories:
            if repo.value[Indexing.CLASS_COMMIT_START.value] is None or repo.value[Indexing.CLASS_COMMIT_END.value] is None:  # We do not find pull request for these repos
                logging.debug("Will not generate output for " + repo.value[Indexing.CLASS_REPO_NAME.value])
            else:  # We find the commits for these repos
                # Get all commits between commits
                commits_hash = self.get_all_commits(auth_info, vyaire_repos_base + repo.value[Indexing.CLASS_REPO_NAME.value], repo.value[Indexing.CLASS_COMMIT_START.value], repo.value[Indexing.CLASS_COMMIT_END.value])
                # Get all pull requests in the repository
                pull_requests = self.get_all_pull_requests(auth_info, vyaire_repos_base + repo.value[Indexing.CLASS_REPO_NAME.value] + QueryItems.pull_state_closed.value, repo.value[Indexing.CLASS_REPO_BRANCH.value])
                # Check PR merge commit sha in all commits
                output_commits = self.commits_in_pull_requests(auth_info, commits_hash, pull_requests, vyaire_repos_base + repo.value[Indexing.CLASS_REPO_NAME.value] + QueryItems.pulls.value)
                # Make the form
                self.make_form(repo.value[Indexing.CLASS_REPO_NAME.value], output_commits)


    def get_all_commits(self, auth_info, input_query, start_commit, end_commit):

        return_hash = {}
        final_commit = end_commit
        index = 0

        # Getting the following commits
        while final_commit != start_commit:
            commit_json = requests.get(input_query + QueryItems.commits.value + final_commit, auth=auth_info).json()

            files = [file['filename'] for file in commit_json['files']]

            last_commit = final_commit
            final_commit = commit_json[PRItems.parents.value][0][PRItems.sha.value]
            title_commit = commit_json['commit']['message']
            return_hash[last_commit] = [index, title_commit, final_commit, '\n'.join(files)]
            index += 1

        # Get the last commit that we do not want to output to the file
        commit_json = requests.get(input_query + QueryItems.commits.value + final_commit, auth=auth_info).json()

        files = [file['filename'] for file in commit_json['files']]

        last_commit = final_commit
        final_commit = commit_json[PRItems.parents.value][0][PRItems.sha.value]
        title_commit = commit_json['commit']['message']
        return_hash[last_commit] = [index, title_commit, final_commit, '\n'.join(files)]

        return return_hash

    def get_all_pull_requests(self, auth_info, input_query, branch_name):
        # Queries all the pull requests
        pr_list_json = requests.get(input_query, auth=auth_info).json()
        cols = [PRItems.number.value, PRItems.url.value, PRItems.title.value, PRItems.user.value, PRItems.merged_at.value, PRItems.merged_commit_sha.value, PRItems.base.value]
        df = pd.DataFrame.from_dict(pr_list_json).query('merged_at.notnull()', engine='python').loc[:, cols]
        users = df[Columns.df_users.value].apply(lambda x: x.get('login'))
        df[Columns.df_users.value] = users

        remove_indexes = []

        # This will get pull requests only if they are in the correct branch
        for index, row in df.iterrows():
            if row[PRItems.base.value][PRItems.ref.value] != branch_name:
                remove_indexes.append(index)

        all_pr_list = df.drop(remove_indexes, axis=0)
        logger.info("Finished getting PR List")

        return all_pr_list

    def commits_in_pull_requests(self, auth_info, commits_hash, pull_requests, input_query):

        length_hash = len(commits_hash)
        pr_list = [None] * length_hash
        indexes = {}

        for index, request in pull_requests.iterrows():
            if request[PRItems.merged_commit_sha.value] in commits_hash:
                reviewers = self.get_review_list(auth_info, input_query + str(request[PRItems.number.value]) + '/reviews')

                commits_hash[request[PRItems.merged_commit_sha.value]].extend([request[PRItems.number.value], request[PRItems.url.value], request[PRItems.user.value], request[PRItems.merged_at.value]])
                index = commits_hash[request[PRItems.merged_commit_sha.value]][0]
                indexes[index] = 1
                pr_list[index] = commits_hash[request[PRItems.merged_commit_sha.value]]
                pr_list[index].insert(1, request[PRItems.merged_commit_sha.value])
                pr_list[index].append(reviewers)

                newline_index = pr_list[index][PRIndexesAfter.commit_title.value].find('\n')
                pr_length = len(pr_list[index][PRIndexesAfter.commit_title.value])
                if newline_index == -1:
                    pr_list[index].append(pr_list[index][PRIndexesAfter.commit_sha.value] + QueryItems.commit_break.value + pr_list[index][PRIndexesAfter.commit_title.value][:pr_length])
                else:
                    pr_list[index].append(pr_list[index][PRIndexesAfter.commit_sha.value] + QueryItems.commit_break.value + pr_list[index][PRIndexesAfter.commit_title.value][:(newline_index+1)])

        # Need to fill the rest of the None portions of pr_list
        for key, value in zip(commits_hash.keys(), commits_hash.values()):
            index = value[PRIndexesAfter.index.value]
            if index not in indexes:
                pr_list[index] = value
                pr_list[index].append(key)

        # Finding the commits that were not hashed to another
        extra_titles = ''
        extra_files = ''
        indexes_to_delete = []

        for i in range(length_hash-1, -1, -1):
            if len(pr_list[i]) != MiscValues.PR_ITEM_LENGTH.value:
                # Need to save the commit title, commit, and files changed
                newline_index = pr_list[i][PRIndexesBefore.commit_title.value].find('\n')
                pr_length = len(pr_list[i][PRIndexesBefore.commit_title.value])
                if newline_index == -1:
                    extra_titles += "\n" + pr_list[i][PRIndexesBefore.commit_sha.value] + QueryItems.commit_break.value + pr_list[i][PRIndexesBefore.commit_title.value][:pr_length]
                else:
                    extra_titles += "\n" + pr_list[i][PRIndexesBefore.commit_sha.value] + QueryItems.commit_break.value + pr_list[i][PRIndexesBefore.commit_title.value][:(newline_index+1)]

                # Where we have the missing pull requests we append the item and delete them later on in the dataframe
                extra_files += "\n" + pr_list[i][PRIndexesBefore.files_changed.value]
                indexes_to_delete.append(i)
            else:
                if len(extra_files) != 0 and len(extra_titles) != 0:
                    pr_list[i][PRIndexesAfter.total_title.value] += extra_titles
                    pr_list[i][PRIndexesAfter.files_changed.value] += extra_files

                    # Get rid of duplicate files here
                    temp_str_files = pr_list[i][PRIndexesAfter.files_changed.value]
                    temp_list_files = temp_str_files.split('\n')
                    final_list_files = list(dict.fromkeys(temp_list_files))
                    final_str_files = '\n'.join(final_list_files)
                    pr_list[i][PRIndexesAfter.files_changed.value] = final_str_files

                extra_titles = ''
                extra_files = ''

        df_list = pd.DataFrame(pr_list)
        df_list.drop(indexes_to_delete, inplace=True)
        df_list.drop(df_list.tail(1).index, inplace=True)

        return df_list

    def get_review_list(self, auth_info, query):
        # This will generate the reviewer list
        review_json = requests.get(query, auth=auth_info).json()
        df = pd.DataFrame.from_dict(review_json).query('state == "APPROVED"', engine='python')
        users = df[Columns.df_users.value].apply(lambda x: x.get('login'))
        df[Columns.df_users.value] = users
        df.drop_duplicates(subset=[Columns.df_users.value], keep='last', inplace=True)
        return_review_list = list(df.loc[:, Columns.df_users.value])
        return '\n'.join(return_review_list)

    def make_form(self, repo_name, input_pr_list):
        # This will make the output form for the repository
        df = input_pr_list.loc[:, [5, 7, 8, 2, 9, 4, 10]]
        col_map = {5:FormHeader.pr_num.value, 7:FormHeader.submitter.value, 8:'Merged Date',
                   2:FormHeader.title.value, 9:'Reviewers', 4:'Files', 10:'Commits'}
        df.rename(columns=col_map, inplace=True)

        df.to_csv(str(repo_name) + '.csv')
        df.to_html(str(repo_name) + '.html')


class ConfigurationParser:
    def __init__(self, input_file):
        dir_list = os.listdir(os.getcwd())
        if input_file in dir_list:
            config = configparser.ConfigParser()
            config.read(input_file)

            # USER in Config file
            global authentication
            authentication[Indexing.USERNAME.value] = config['USER']['username'] if config['USER']['username'] != 'None' and config['USER']['username'] != 'none' else None
            authentication[Indexing.PASSWORD.value] = config['USER']['password'] if config['USER']['password'] != 'None' and config['USER']['password'] != 'none' else None

            # COMMITS in Config file
            fabian_gui_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_gui']))
            fabian_monitor_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_monitor']))
            fabian_controller_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_controller']))
            fabian_alarm_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_alarm']))
            fabian_blender_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_blender']))
            fabian_power_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_power']))
            fabian_power_evo_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_power_evo']))
            fabian_hfo_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_hfo']))
            fabian_controller_bootloader_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_controller_bootloader']))
            fabian_alarm_bootloader_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_alarm_bootloader']))
            fabian_monitor_bootloader_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_monitor_bootloader']))
            fabian_hfo_bootloader_commits = self.check_commits(ast.literal_eval(config['COMMITS']['fabian_hfo_bootloader']))

            # BRANCH in Config file
            fabian_gui_branch = config['BRANCH']['fabian_gui'] if config['BRANCH']['fabian_gui'] != 'None' and config['BRANCH']['fabian_gui'] != 'none' else 'master'
            fabian_monitor_branch = config['BRANCH']['fabian_monitor'] if config['BRANCH']['fabian_monitor'] != 'None' and config['BRANCH']['fabian_monitor'] != 'none' else 'master'
            fabian_controller_branch = config['BRANCH']['fabian_controller'] if config['BRANCH']['fabian_controller'] != 'None' and config['BRANCH']['fabian_controller'] != 'none' else 'master'
            fabian_alarm_branch = config['BRANCH']['fabian_alarm'] if config['BRANCH']['fabian_alarm'] != 'None' and config['BRANCH']['fabian_alarm'] != 'none' else 'master'
            fabian_blender_branch = config['BRANCH']['fabian_blender'] if config['BRANCH']['fabian_blender'] != 'None' and config['BRANCH']['fabian_blender'] != 'none' else 'master'
            fabian_power_branch = config['BRANCH']['fabian_power'] if config['BRANCH']['fabian_power'] != 'None' and config['BRANCH']['fabian_power'] != 'none' else 'master'
            fabian_power_evo_branch = config['BRANCH']['fabian_power_evo'] if config['BRANCH']['fabian_power_evo'] != 'None' and config['BRANCH']['fabian_power_evo'] != 'none' else 'master'
            fabian_hfo_branch = config['branch']['fabian_hfo'] if config['BRANCH']['fabian_power_evo'] != 'None' and config['BRANCH']['fabian_power_evo'] != 'none' else 'master'
            fabian_controller_bootloader_branch = config['BRANCH']['fabian_controller_bootloader'] if config['BRANCH']['fabian_controller_bootloader'] != 'None' and config['BRANCH']['fabian_controller_bootloader'] != 'none' else 'master'
            fabian_alarm_bootloader_branch = config['BRANCH']['fabian_alarm_bootloader'] if config['BRANCH']['fabian_alarm_bootloader'] != 'None' and config['BRANCH']['fabian_alarm_bootloader'] != 'none' else 'master'
            fabian_monitor_bootloader_branch = config['BRANCH']['fabian_monitor_bootloader'] if config['BRANCH']['fabian_monitor_bootloader'] != 'None' and config['BRANCH']['fabian_monitor_bootloader'] != 'none' else 'master'
            fabian_hfo_bootloader_branch = config['BRANCH']['fabian_hfo_bootloader'] if config['BRANCH']['fabian_hfo_bootloader'] != 'None' and config['BRANCH']['fabian_hfo_bootloader'] != 'none' else 'master'

            # Copying over to the class
            Repositories.fabian_gui.value[Indexing.CLASS_COMMIT_START.value] = fabian_gui_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_gui.value[Indexing.CLASS_COMMIT_END.value] = fabian_gui_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_gui.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_gui_branch

            Repositories.fabian_monitor.value[Indexing.CLASS_COMMIT_START.value] = fabian_monitor_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_monitor.value[Indexing.CLASS_COMMIT_END.value] = fabian_monitor_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_monitor.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_monitor_branch

            Repositories.fabian_controller.value[Indexing.CLASS_COMMIT_START.value] = fabian_controller_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_controller.value[Indexing.CLASS_COMMIT_END.value] = fabian_controller_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_controller.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_controller_branch

            Repositories.fabian_alarm.value[Indexing.CLASS_COMMIT_START.value] = fabian_alarm_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_alarm.value[Indexing.CLASS_COMMIT_END.value] = fabian_alarm_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_alarm.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_alarm_branch

            Repositories.fabian_blender.value[Indexing.CLASS_COMMIT_START.value] = fabian_blender_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_blender.value[Indexing.CLASS_COMMIT_END.value] = fabian_blender_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_blender.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_blender_branch

            Repositories.fabian_power.value[Indexing.CLASS_COMMIT_START.value] = fabian_power_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_power.value[Indexing.CLASS_COMMIT_END.value] = fabian_power_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_power.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_power_branch

            Repositories.fabian_power_evo.value[Indexing.CLASS_COMMIT_START.value] = fabian_power_evo_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_power_evo.value[Indexing.CLASS_COMMIT_END.value] = fabian_power_evo_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_power_evo.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_power_evo_branch

            Repositories.fabian_hfo.value[Indexing.CLASS_COMMIT_START.value] = fabian_hfo_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_hfo.value[Indexing.CLASS_COMMIT_END.value] = fabian_hfo_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_hfo.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_hfo_branch

            Repositories.fabian_controller_bootloader.value[Indexing.CLASS_COMMIT_START.value] = fabian_controller_bootloader_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_controller_bootloader.value[Indexing.CLASS_COMMIT_END.value] = fabian_controller_bootloader_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_controller_bootloader.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_controller_bootloader_branch

            Repositories.fabian_alarm_bootloader.value[Indexing.CLASS_COMMIT_START.value] = fabian_alarm_bootloader_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_alarm_bootloader.value[Indexing.CLASS_COMMIT_END.value] = fabian_alarm_bootloader_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_alarm_bootloader.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_alarm_bootloader_branch

            Repositories.fabian_monitor_bootloader.value[Indexing.CLASS_COMMIT_START.value] = fabian_monitor_bootloader_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_monitor_bootloader.value[Indexing.CLASS_COMMIT_END.value] = fabian_monitor_bootloader_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_monitor_bootloader.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_monitor_bootloader_branch

            Repositories.fabian_hfo_bootloader.value[Indexing.CLASS_COMMIT_START.value] = fabian_hfo_bootloader_commits[Indexing.CONFIG_COMMIT_START.value]
            Repositories.fabian_hfo_bootloader.value[Indexing.CLASS_COMMIT_END.value] = fabian_hfo_bootloader_commits[Indexing.CONFIG_COMMIT_END.value]
            Repositories.fabian_hfo_bootloader.value[Indexing.CLASS_REPO_BRANCH.value] = fabian_hfo_bootloader_branch
        else:
            logger.warning("Missing INI file")


    def check_commits(self, input_commits):
        length = len(input_commits)
        temp_return = input_commits

        for commit in input_commits:
            if commit is None or len(commit) != MiscValues.COMMIT_LENGTH.value:
                temp_return = [None] * length
                break

        return temp_return

def main():
    logger.info("Pull Request Form Start:")

    # INI file parser
    config = ConfigurationParser("form.ini")

    # Pull Request Generated Form
    global authentication
    auth_info = tuple(authentication)
    if auth_info[0] is None or auth_info[1] is None:
        logger.warning("No authentication!")
    else:
        form = PullRequestForm()
        form.generate_form(auth_info)


if __name__ == "__main__":
   main()
