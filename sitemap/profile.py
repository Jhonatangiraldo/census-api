from jinja2 import Environment, FileSystemLoader
import unicodedata
import psycopg2
import re
import os.path

EXCLUDED_SUMMARY_LEVELS = ['190'] # if they don't work, put 'em here

def write_profile_sitemaps(output_dir,db_connect_string='postgresql://census:censuspassword@localhost:5432/census'):
    ''' Builds sitemap XML files for all summary levels. Each XML file contains pages for one
    summary level, with a maximum of 50,000 URLs.

    params: none
    return: none

    '''
    sitemaps_created = []

    with psycopg2.connect(db_connect_string) as conn:
        for summary_level in query_all_levels(conn):
            if summary_level not in EXCLUDED_SUMMARY_LEVELS:
                print("querying level {}".format(summary_level))
                results = query_one_level(summary_level, conn)
                urls = []

                for result in results:
                    (display_name, full_geoid) = result
                    urls.append(build_url(display_name, full_geoid))

                num_urls = len(urls)

                # If there are <= 50k URLs, write them immediately
                if num_urls <= 50000:
                    filename = 'sitemap_' + summary_level + '.xml'
                    f = open(os.path.join(output_dir,filename), 'w')

                    f.write(build_sitemap(urls))

                    print('Wrote sitemap to file %s' % (filename))
                    sitemaps_created.append(filename)
                    f.close()

                # Otherwise, split up the URLs into groups of 50,000
                else:
                    num_files = (num_urls // 50000) + 1

                    for i in range(num_files):
                        filename = 'sitemap_' + summary_level + '_' + str(i + 1) + '.xml'
                        f = open(os.path.join(output_dir,filename), 'w')
                        f.write(build_sitemap(urls[i * 50000 : (i + 1) * 50000]))
                        print('Wrote sitemap to file %s' % (filename))
                        sitemaps_created.append(filename)
                        f.close()

    write_master_sitemap(output_dir, sitemaps_created)

def write_master_sitemap(output_dir,files):
    files = files[:]
    files.extend(['sitemap_tables.xml','topics/sitemap.xml'])
    urls = ['https://censusreporter.org/{}'.format(f) for f in files]

    with open(os.path.join(output_dir,'sitemap.xml'),'w') as f:
        f.write(build_sitemap(urls))
        print('wrote index sitemap.xml file')

def build_sitemap(page_data):
    ''' Builds sitemap from template in sitemap.xml using data provided
    in page_data.

    params: page_data = list of page URLs
    returns: XML template with the page URLs

    '''

    env = Environment(loader = FileSystemLoader('.'))
    template = env.get_template('sitemap.xml')

    return template.render(pages = page_data)


def query_all_levels(db_conn):
    ''' Queries database to get list of all sumlevels

    params: none
    returns: list of all sumlevels (strings)

    '''

    with db_conn.cursor() as cur:
        q = "SELECT DISTINCT sumlevel FROM tiger2020.census_name_lookup order by sumlevel;"
        cur.execute(q)
        results = cur.fetchall()
        # Format of results is [('000',), ('001',), ...]
        # so we make it into a straight list ['000', '001', ...]

        results_list = [c[0] for c in results]

        return results_list


def query_one_level(level, db_conn):
    ''' Queries database for one sumlevel ("level")

    params: level = string of the summary level code (e.g., "040")
    return: all results found as a list of tuples
            (sumlevel, display_name, full_geoid)

    '''

    with db_conn.cursor() as cur:
        q = "SELECT display_name, full_geoid from tiger2020.census_name_lookup where sumlevel = '%s' order by full_geoid" % (level)
        cur.execute(q)
        results = cur.fetchall()

        return results


def build_url(display_name, full_geoid):
    ''' Builds the censusreporter URL out of name and geoid.
    Format: https://censusreporter.org/profiles/full_geoid-display_name/"

    params: display_name = (string) name of the area,
            full_geoid = (string) geoid code for the URL
    return: full URL of the relevant page

    >>> build_url("Indiana", "04000US18")
    "https://censusreporter.org/profiles/04000US18-indiana"

    >>> build_url("Columbus, IN Metro Area", "31000US18020")
    "https://censusreporter.org/profiles/31000US18020-columbus-in-metro-area"

    '''

    new_name = slugify(display_name)
    return "https://censusreporter.org/profiles/" + full_geoid + "-" + new_name + "/"

# lifted from Django to make slugs common between sitemap and website
def slugify(value, allow_unicode=False):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


def main():
    write_profile_sitemaps('.')


# Some tests
assert build_url("Indiana", "04000US18") == "https://censusreporter.org/profiles/04000US18-indiana/"
assert build_url("Columbus, IN Metro Area", "31000US18020") == "https://censusreporter.org/profiles/31000US18020-columbus-in-metro-area/"


if __name__ == "__main__":
    main()
