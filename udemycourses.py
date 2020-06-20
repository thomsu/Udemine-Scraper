from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException

import time
import pandas as pd


def scraper(search_term='python machine learning', filter_category='Machine Learning', previous_links=[]):
    """

    This scrapes udemy.com for courses and reviews given a term to execute a search and a category to filter.
    To ensure that it works properly, visit udemy.com beforehand to find the appropriate search_term and filter_category.
    Only choose one of the categories from the top most panel on the page containing a listing of the results.
    Provide a list of links, if you so choose, that should be left out from the scrape job as previous_links.
    It returns 2 Pandas DataFrame; the first one contains the reviews and the other is a description of the courses.
    The default for the input variables are:
    search_term='python machine learning'
    filter_term='Machine Learning'
    previous_links=[]

    """
# ===========================Preprocessing=======================================
    cols = ['course_link', 'customer_name', 'time_posted', 'review', 'ratings']
    df = pd.DataFrame(columns=cols)  # empty DataFrame for reviews
    courses = list()  # empty list for course details
    visited_links = list()  # to keep tab on links that have been scraped or checked to not meet the requirement

    # validate input data types
    if not isinstance(search_term, str):
        raise TypeError(
            f"Input variable, search_term, should be a string and not type {type(search_term)}.")
    if not isinstance(filter_category, str):
        raise TypeError(
            f"Input variable, filter_category, should be a string and not type {type(filter_category)}.")
    if previous_links and not isinstance(previous_links, list):
        raise TypeError(
            "Input variable, previous_links, should be a list of previous visited links.")

    visited_links.extend(previous_links)  # merge user given links into one list
# ===========================Start Searching=====================================
    browser = webdriver.Chrome()
    browser.get('http://www.udemy.com')

    try:
        elem = WebDriverWait(browser, 5).until(EC.visibility_of_element_located((By.NAME, "q")))
    except TimeoutException:
        print("Taking much too long to load. Please check your internet connection.")

    elem.send_keys(search_term + Keys.RETURN)

    # check for issues that the search yield no results.
    try:
        WebDriverWait(browser, 5).until(EC.visibility_of_any_elements_located(
            (By.XPATH, "//div[@class='panel--content-wrapper--1yFBX']//fieldset[@name='Topic']")))
    except TimeoutException:
        print("Encounter a problem retrieving search results. Please check if search_term and filter_category are valid.")

    add_filter(browser, filter_category)
# =================First Filtered Search Results Page Returned===================
    time.sleep(2)
    # access links of search results
    courses_links = browser.find_elements_by_class_name("udlite-custom-focus-visible")
    links = [c.get_attribute("href") for c in courses_links]
    nextpage = get_nextpage(browser)  # access link to next page of search results
# =======================Iteratively Scrape Links================================
    page_count = 1
    df, courses = scrape_links_navigator(browser, df, cols, courses, links, visited_links)
    print(
        f'Finished with all course listings on page {page_count}! {len(courses)} {search_term} courses scraped so far.')

    while nextpage:
        df, courses, page_count, nextpage = listings_page_iterator(browser, nextpage, page_count, df,
                                                                   cols, courses, links, visited_links)
        print(
            f'Finished with all course listings on page {page_count}! {len(courses)} {search_term} courses scraped so far.')

    browser.quit()
    print('All done!')
    return df, pd.DataFrame(courses)


def add_filter(browser, filter_category):
    """

    This adds filter to narrow down the search results using the filter_category provided.
    It also adds a filter to limit the language of the courses to English.

    """
    # attempt to expand the Topic menu list
    while True:
        try:
            expandlist = browser.find_element_by_xpath(
                "//label[contains(text(),'Topic')]/following-sibling::node()//label[@role='button']")
            expandlist.click()
            break
        except NoSuchElementException:
            expose_filter_menu(browser, 'Topic')
        except ElementClickInterceptedException:
            browser.execute_script("arguments[0].click();", expandlist)
            break
    # find the checkbox that match the filter category and attempt to mark it
    filtercat = browser.find_elements_by_xpath(
        "//div[@class='panel--content-wrapper--1yFBX']//fieldset[@name='Topic']//span[@class='filter--count--33UW8']/parent::node()")
    indc = [cat.text.split("(")[0] for cat in filtercat].index(filter_category)
    checkbox = browser.find_elements_by_xpath(
        "//div[@class='panel--content-wrapper--1yFBX']//fieldset[@name='Topic']//input")[indc]
    try:
        checkbox.click()
    except ElementClickInterceptedException:
        browser.execute_script("arguments[0].click();", checkbox)

    expose_filter_menu(browser, 'Language')
    # attempt to mark the English language checkbox
    filterlang = browser.find_elements_by_xpath(
        "//div[@class='panel--content-wrapper--1yFBX']//fieldset[@name='Language']//span[@class='filter--count--33UW8']/parent::node()")
    indl = [lang.text.split("(")[0] for lang in filterlang].index('English')
    checkbox = browser.find_elements_by_xpath(
        "//div[@class='panel--content-wrapper--1yFBX']//fieldset[@name='Language']//input")[indl]
    try:
        checkbox.click()
    except ElementClickInterceptedException:
        browser.execute_script("arguments[0].click();", checkbox)


def get_nextpage(browser):
    """

    returns the link to the next page of search results if any is found

    """

    try:
        return browser.find_element_by_xpath(
            "//div[@class='pagination--container--2wc6Z']//a[@data-page='+1']").get_attribute("href")
    except NoSuchElementException:
        return None


def scrape_links_navigator(browser, df, cols, courses, links, visited_links):
    """

    Given a list of course links, this navigates and iterate through the list.

    """

    for link in links:
        if link not in visited_links:  # scrape links only if not in list
            browser.get(link)
            proceed, courses = course_scraper(browser, courses, link)
            # if requirements are not met in course scraper, the link is not to be scraped.
            if proceed:
                df = review_scraper(browser, df, cols, link)
            visited_links.append(link)

    return df, courses


def listings_page_iterator(browser, nextpage, page_count, df, cols, courses, links, visited_links):
    """

    For course listings page 2 to the last page, this grabs the list of course links and the next page of listings.

    """

    browser.get(nextpage)
    page_count += 1
    # check for new search results and next search result link.
    try:
        WebDriverWait(browser, 5).until(EC.visibility_of_any_elements_located(
            (By.CLASS_NAME, "udlite-custom-focus-visible")))
    except TimeoutException:
        nextpage = get_nextpage(browser)
        return df, courses  # end scraper if no new search results and no next search result link

    courses_links = browser.find_elements_by_class_name("udlite-custom-focus-visible")
    links = [c.get_attribute("href") for c in courses_links]
    nextpage = get_nextpage(browser)

    df, courses = scrape_links_navigator(browser, df, cols, courses, links, visited_links)

    return df, courses, page_count, nextpage


def course_scraper(browser, courses, link):
    """

    This scrapes all details related to the description of the course.

    """

    course = dict()
# =========================Minimum Requirement Check=============================
    WebDriverWait(browser, 5).until(EC.presence_of_element_located(
        (By.XPATH, "//div[contains(@data-content-group,'Landing Page')]//div[@data-purpose='enrollment']")))
    enrolled = browser.find_element_by_xpath(
        "//div[contains(@data-content-group,'Landing Page')]//div[@data-purpose='enrollment']").text.split(" ", 1)[0]
    try:
        num_of_reviews = browser.find_element_by_xpath(
            "//div[contains(@data-content-group,'Landing Page')]//div[@class='rate-count']").text.split()[1][1:]
    except NoSuchElementException:
        return False, courses
    language = browser.find_element_by_xpath(
        "//div[contains(@data-content-group,'Landing Page')]//div[@class='clp-lead__locale']").text
    # check if students enrolled, number of reviews and language requirements are met
    if int(enrolled.replace(",", "")) < 500 or int(num_of_reviews.replace(",", "")) < 50 or language != "English":
        return False, courses  # skip scraping if not
# ===============================Scrape Page=====================================
    course['link'] = link
    course['title'] = browser.find_element_by_xpath("//h1").text
    # expand topic section if it is possible and capture info
    expand_section(
        browser, "//div[@class='what-you-get']//button[contains(@class,'js-simple-collapse-more-btn')]")
    topics = browser.find_elements_by_class_name("what-you-get__text")
    course['topics'] = ', '.join([t.text for t in topics])
    # expand course description section if it is possible and capture info
    expand_section(
        browser, "//div[contains(@data-purpose,'course-description')]//button[contains(@class,js-simple-collapse-more-btn)]")
    summary = browser.find_elements_by_xpath(
        "//div[@class='description__title']/following-sibling::*//*")
    course['summary'] = '\n'.join([s.text for s in summary[:-3]])

    course['number_of_lectures'] = browser.find_element_by_xpath("//span[@class='dib']").text
    course['total_video_duration'] = browser.find_element_by_xpath(
        "//span[@class='curriculum-header-length']").text
    # expand course lectures if it is possible
    expand_toggle(
        browser, '//a[@data-purpose="load-full-curriculum" or @data-purpose="toggle-section"]')
    expand_toggle(browser, '//a[@class="sections-toggle"]')
    titles = browser.find_elements_by_xpath(
        "//div[@data-purpose='course-curriculum']//div[@class='title']")
    duration = browser.find_elements_by_xpath(
        "//div[@data-purpose='course-curriculum']//div[@class='details']")
    # attempt to capture lecture titles and durations; if encountered a change of the DOM, wait 2 seconds
    while True:
        try:
            course['lectures_breakdown'] = list(
                zip([t.text for t in titles], [d.text for d in duration]))
        except StaleElementReferenceException:
            time.sleep(2)
            continue
        break

    course['original_price'] = browser.find_element_by_xpath(
        "//div[@data-purpose='course-old-price-text']//s/span").text
    # find out if there is one or more instructors information and process them separately
    instructors = browser.find_elements_by_class_name("instructor--instructor--2qudS")
    if len(instructors) > 1:
        # add '-&-' between the names of instructors
        course['instructor_name'] = ' -&- '.join([i.find_element_by_class_name(
            "instructor--title__link--1NJ6S").text for i in instructors])
        course['instructor_bio'], stats = get_bio_stats(browser)
        # create a list of different instructors for each stat
        course['group_instructor_rating'] = stats[::4]
        course['group_reviews'] = stats[1::4]
        course['group_students'] = stats[2::4]
        course['group_courses'] = stats[3::4]

    else:
        course['instructor_name'] = instructors[0].find_element_by_class_name(
            "instructor--title__link--1NJ6S").text
        course['instructor_bio'], stats = get_bio_stats(browser)
        course['instructor_rating'], course['total_reviews'], course['total_students'], course['total_courses'] = stats[0], stats[1], stats[2], stats[3]

    courses.append(course)
    return True, courses


def review_scraper(browser, df, cols, link):
    """

    This scrapes all details about the reviews of a course.

    """
    # repeat the specified number of times to expand the review section
    repeats = 5
    while repeats:
        try:
            browser.find_element_by_xpath(
                "//button[@data-purpose='show-more-review-button']").click()
        except NoSuchElementException:
            break
        except StaleElementReferenceException:
            break
        repeats -= 1
    # expand to reveal the complete review of long reviews that are partially hidden
    see_more = browser.find_elements_by_xpath(
        "//div[@data-purpose='landing-page-review-list']//button[contains(@class,'view-more-container--view-more__collapse-btn--1bVN9 btn btn-link')]")
    if see_more:
        for s in see_more:
            try:
                s.click()
            except ElementClickInterceptedException:
                browser.execute_script("arguments[0].click();", s)

    posts = browser.find_elements_by_xpath(
        "//div[@data-purpose='landing-page-review-list']//div[@data-purpose='review-comment-content']")
    review = [post.text for post in posts]
    course_link = [link]*len(review)

    customers = browser.find_elements_by_xpath(
        "//div[@data-purpose='landing-page-review-list']//div[@data-purpose='review-detail-user-name']")
    customer_name = [c.text for c in customers]

    stars = browser.find_elements_by_xpath(
        "//div[@data-purpose='landing-page-review-list']//div[@data-purpose='star-rating-shell']")
    ratings = [s.get_attribute("aria-label")[8:] for s in stars]

    posted_when = browser.find_elements_by_xpath(
        "//div[@data-purpose='landing-page-review-list']//div[@class='individual-review--detail-created--1liJC']")
    time_posted = [w.text for w in posted_when]

    return pd.concat([df, pd.DataFrame(list(zip(course_link, customer_name, time_posted, review, ratings)), columns=cols)], ignore_index=True)


def expand_section(browser, path):
    """

    attempts to expand a section and at the same time handles exceptions thrown

    """

    try:
        browser.find_element_by_xpath(path).click()
    except NoSuchElementException:
        pass
    except ElementClickInterceptedException:
        see_more_section = browser.find_element_by_class_xpath(path)
        browser.execute_script("arguments[0].click();", see_more_section)


def expand_toggle(browser, path):
    """

    wait for element to be visible before expand a toggle; also handles exceptions thrown

    """

    try:
        toggle = WebDriverWait(browser, 5).until(
            EC.visibility_of_element_located((By.XPATH, path)))
        toggle.click()
    except TimeoutException:
        pass
    except ElementClickInterceptedException:
        browser.execute_script("arguments[0].click();", toggle)


def get_bio_stats(browser):
    """

    locate and capture instructor bio and stats information

    """

    see_more_bio = browser.find_elements_by_class_name(
        "instructor--view-more-wrapper__button--2egB6")
    for s in see_more_bio:
        try:
            s.click()
        except ElementClickInterceptedException:
            browser.execute_script("arguments[0].click();", s)

    bio = browser.find_elements_by_xpath(
        "//div[@class='instructor--instructor--2qudS']//div[@data-purpose='safely-set-inner-html:trusted-html:content']//p")
    instructor_bio = '\n'.join([b.text.strip() for b in bio])

    stats = browser.find_elements_by_xpath(
        "//span[@class='instructor--instructor__stat-value--2Kwe1']")
    stats = [s.text for s in stats]

    return instructor_bio, stats


def expose_filter_menu(browser, filter_by):
    """

    find the text of the label that matches with what is provided and attempt to expose the menu

    """

    exposemenu = browser.find_elements_by_xpath(
        "//label[contains(@class,'js-panel-toggler  panel--label--qoWJs') and @aria-expanded='false']")
    ind = [fltr.text for fltr in exposemenu].index(filter_by)
    try:
        exposemenu[ind].click()
    except ElementClickInterceptedException:
        browser.execute_script("arguments[0].click();", exposemenu[ind])
