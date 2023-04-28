"""
python: 3.11.0
streamlit: 1.21.0
"""

from collections import OrderedDict
import requests, socketio, asyncio
import streamlit as st
import uuid

## Source for pagination: https://gist.github.com/treuille/2ce0acb6697f205e44e3e0f576e810b7
def paginator(label, items, items_per_page=10, on_sidebar=True, new_loc=True):
    """Lets the user paginate a set of items.

    Parameters
    ----------
    label : str
        The label to display over the pagination widget.
    items : Iterator[Any]
        The items to display in the paginator.
    items_per_page: int
        The number of items to display per page.
    on_sidebar: bool
        Whether to display the paginator widget on the sidebar.

    Returns
    -------
    Iterator[Tuple[int, Any]]
        An iterator over *only the items on that page*, including
        the item's index.

    Example
    -------
    This shows how to display a few pages of fruit.
    >>> fruit_list = [
    ...     'Kiwifruit', 'Honeydew', 'Cherry', 'Honeyberry', 'Pear',
    ...     'Apple', 'Nectarine', 'Soursop', 'Pineapple', 'Satsuma',
    ...     'Fig', 'Huckleberry', 'Coconut', 'Plantain', 'Jujube',
    ...     'Guava', 'Clementine', 'Grape', 'Tayberry', 'Salak',
    ...     'Raspberry', 'Loquat', 'Nance', 'Peach', 'Akee'
    ... ]
    ...
    ... for i, fruit in paginator("Select a fruit page", fruit_list):
    ...     st.write('%s. **%s**' % (i, fruit))
    """

    # Figure out where to display the paginator
    if on_sidebar:
        location = st.sidebar.empty()
    else:
        location = st.empty()
    # Display a pagination selectbox in the specified location.
    items = list(items)
    # n_pages = len(items)
    n_pages = (len(items) - 1) // items_per_page + 1
    page_format_func = lambda i: "Page %s" % i
    if new_loc:
        page_number = location.selectbox(label, range(n_pages), format_func=page_format_func)
    else:
        page_number = location.selectbox(label, range(n_pages), format_func=page_format_func, key=str(uuid.uuid1()))

    # Iterate over the items in the page to let the user display them.
    min_index = page_number * items_per_page
    max_index = min_index + items_per_page
    import itertools
    return itertools.islice(enumerate(items), min_index, max_index)

## GET the jobs from the Flask server ordered on key 'jobs'
jobs = requests.get('http://127.0.0.1:5000/.json?orderBy=%22$key%22&equalTo="jobs"')
jobs = jobs.json()
jobs_list = []
for job in jobs:
    jobs_list.extend(job['jobs'].keys())

## get the data ordered on key 'locations'
location = requests.get('http://127.0.0.1:5000/.json?orderBy=%22$key%22&equalTo="locations"')
location = location.json()
location_list = []
for l in location:
    location_list.extend(l['locations'])
location_list = sorted(list(set(location_list)))

jobs_list = sorted(list(set(jobs_list)))
st.set_page_config(layout="wide")
st.write('<style>div.block-container{padding-top:2rem;}</style>', unsafe_allow_html=True)
st.title('JobMatch')

cols = st.columns(2)
with cols[0]:
    selected_type = st.selectbox('Select Role', jobs_list)
    selected_locations = st.multiselect('Select Location', location_list)
    number = st.number_input('Insert minimum number of jobs available for selected role', value = 1, min_value = 1)

with cols[1]:
    placeholder = st.empty()
jobs_info = requests.get('http://127.0.0.1:5000/.json?orderBy=%22jobs/' + selected_type +'%22' + '&startAt=' + str(number))
jobs_info = jobs_info.json()

## creating the view for display of company name and details
def create_company_view(jobs_desc, new_loc=True):
    if not isinstance(jobs_desc, list):
        jobs_desc = [jobs_desc]
    companies_info = {}
    for val in jobs_desc:
        if 'jobs' in val:
            if selected_locations:
                if 'locations' in val:
                    if selected_type in val['jobs'] and set(selected_locations).intersection(set(val['locations'])):
                        if 'company_name' in val:
                            companies_info[val['company_name']] = {key: val[key] for key in val.keys() & {'headline', 'website', 'about', 'locations'}}
            else:
                if selected_type in val['jobs']:
                    if 'company_name' in val:
                        companies_info[val['company_name']] = {key: val[key] for key in val.keys() & {'headline', 'website', 'about', 'locations'}}
    companies_info = OrderedDict(sorted(companies_info.items()))
    with cols[1]:
        with placeholder.container():
            if companies_info:
                paginator_iterator = paginator("Select a page", companies_info.keys(), on_sidebar=False, new_loc=new_loc)
                for i, company in paginator_iterator:
                    with st.expander(company):
                        for k in companies_info[company]:
                            if k != 'company_name':
                                if k == 'locations':
                                    st.markdown('Locations: ' + ', '.join(companies_info[company][k]))
                                else:
                                    st.markdown(companies_info[company][k])
                return jobs_desc
    return None

if jobs_info:
    jobs_info = create_company_view(jobs_info)

async def run_socketio(url='http://127.0.0.1:5000'):
    sio = socketio.AsyncClient()
    @sio.event
    def connect():
        print('connection established')

    @sio.event
    def disconnect():
        print('disconnected from server')

    ## receives the event from client and updates the company info
    @sio.on('updated company info')
    def on_update(data):
        update_company(data)

    def update_company(data):
        jobs_info = requests.get('http://127.0.0.1:5000/.json?orderBy=%22jobs/' + selected_type +'%22' + '&startAt=' + str(number))
        jobs_info = jobs_info.json()
        create_company_view(jobs_info, new_loc=False)

    await sio.connect(url)
    await sio.wait()

if __name__ == '__main__':
    asyncio.run(run_socketio())