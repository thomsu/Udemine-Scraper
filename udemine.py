from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.common.exceptions import StaleElementReferenceException, ElementNotInteractableException

import time
from tqdm import tqdm
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
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    options.add_argument('window-size=1920x1080')
    options.add_argument("disable-gpu")
    browser = webdriver.Chrome('chromedriver', chrome_options=options)
    browser.get('http://www.udemy.com')

    print('Sending search query...')
    message = "Taking much too long to load. Please check your internet connection."
    elem = WebDriverWait(browser, 3).until(
        EC.visibility_of_element_located((By.NAME, "q")), message=message)
    elem.send_keys(search_term + Keys.RETURN)

    time.sleep(1)
    # check for issues that the search yield no results.
    message = "Encounter a problem while attempting to refine search results. Unable to locate filter."
    WebDriverWait(browser, 3).until(EC.visibility_of_any_elements_located(
        (By.XPATH, "//div[@class='filter-panel--sidebar--L2lAU'] | //button[contains(@class,'filter-button--filter-button--y-iVA')]")), message=message)

    try:
        filterbutton = browser.find_element_by_xpath(
            "//button[contains(@class,'filter-button--filter-button--y-iVA')]")
        browser.execute_script("arguments[0].click();", filterbutton)
    except NoSuchElementException:
        panel_filter_add(browser, filter_category)
    else:
        overlay_filter_add(browser, filter_category)
# =================First Filtered Search Results Page Returned===================
    time.sleep(1)
    # access links of search results
    courses_links = browser.find_elements_by_xpath(
        "//div[@class='course-list--container--3zXPS']//a[contains(@class,'udlite-custom-focus-visible')] | //div[@data-purpose='search-course-cards']//a")
    links = [c.get_attribute("href") for c in courses_links]
    nextpage = get_nextpage(browser)  # access link to next page of search results

# =======================Iteratively Scrape Links================================
    page_count = 1
    print(f'Iterating through page {page_count} of filtered search results...')
    df, courses = scrape_links_navigator(browser, df, cols, courses, links, visited_links)
    print(
        f'Finished with all course listings on page {page_count}! {len(courses)} courses scraped so far.')

    while nextpage:
        print(f'Iterating through page {page_count + 1} of filtered search results...')
        df, courses, page_count, nextpage = listings_page_iterator(browser, nextpage, page_count, df,
                                                                   cols, courses, links, visited_links)
        print(
            f'Finished with all course listings on page {page_count}! {len(courses)} courses scraped so far.')

    browser.quit()
    print('All done!')
    return df, pd.DataFrame(courses)


def panel_filter_add(browser, filter_category):
    """

    This adds filter to narrow down the search results using the filter_category provided.
    It also adds a filter to limit the language of the courses to English.

    """
    print('Filtering search results...')
    # attempt to expand the Topic menu list
    while True:
        try:
            expandlist = WebDriverWait(browser, 3).until(EC.visibility_of_element_located(
                (By.XPATH, "//label[contains(text(),'Topic')]/following-sibling::node()//label[@role='button']")))
            browser.execute_script("arguments[0].click();", expandlist)
            break
        except TimeoutException:
            try:
                expose_filter_menu(browser, 'Topic')
                continue
            except ValueError:
                break

    # find the checkbox that match the filter category and attempt to mark it
    filtercat = browser.find_elements_by_xpath(
        "//div[@class='panel--content-wrapper--1yFBX']//fieldset[@name='Topic']//span[@class='filter--count--33UW8']/parent::node()")
    try:
        indc = [cat.text.split("(")[0] for cat in filtercat].index(filter_category)
    except ValueError:
        catlist = ', '.join([cat.text.split("(")[0] for cat in filtercat])
        browser.quit()
        raise ValueError(
            f"Encountered a problem while filtering search results. Unable to filter by the category given. Categories::{catlist}")

    checkbox = browser.find_elements_by_xpath(
        "//div[@class='panel--content-wrapper--1yFBX']//fieldset[@name='Topic']//input")[indc]
    browser.execute_script("arguments[0].click();", checkbox)

    time.sleep(1)
    gotofix = browser.find_element_by_xpath(
        "//div[@class='filter-button-container--button-bar--DU5FK'] | //div[@class='filter-panel--container--aq5nC']")
    browser.execute_script("arguments[0].scrollIntoView();", gotofix)

    time.sleep(1)
    expose_filter_menu(browser, 'Language')
    # attempt to mark the English language checkbox
    filterlang = browser.find_elements_by_xpath(
        "//div[@class='panel--content-wrapper--1yFBX']//fieldset[@name='Language']//span[@class='filter--count--33UW8']/parent::node()")
    indl = [lang.text.split("(")[0] for lang in filterlang].index('English')
    checkbox = browser.find_elements_by_xpath(
        "//div[@class='panel--content-wrapper--1yFBX']//fieldset[@name='Language']//input")[indl]
    browser.execute_script("arguments[0].click();", checkbox)

    time.sleep(1)
    gotofix = browser.find_element_by_xpath(
        "//div[@class='filter-button-container--button-bar--DU5FK'] | //div[@class='filter-panel--container--aq5nC']")
    browser.execute_script("arguments[0].scrollIntoView();", gotofix)


def get_nextpage(browser):
    """

    returns the link to the next page of search results if any is found

    """

    try:
        nextpage = WebDriverWait(browser, 3).until(EC.presence_of_element_located(
            (By.XPATH, "//div[@class='pagination--container--2wc6Z']//a[@data-page='+1'] | //span[@aria-label='Next']/parent::node()"))).get_attribute("href")
    except (NoSuchElementException, TimeoutException):
        return None
    try:
        attribute_value = browser.find_element_by_xpath(
            "//ul[@class='pagination pagination-expanded']/li[last()]").get_attribute("class")
    except NoSuchElementException:
        return nextpage
    else:
        if attribute_value:
            return None
        return nextpage


def scrape_links_navigator(browser, df, cols, courses, links, visited_links):
    """

    Given a list of course links, this navigates and iterate through the list.

    """

    for link in tqdm(links):
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
    # trick to force javascript to expose elements in the DOM
    while True:
        try:
            time.sleep(1)
            gotofix = browser.find_element_by_xpath(
                "//div[@class='filter-button-container--button-bar--DU5FK'] | //div[@class='filter-panel--container--aq5nC']")
            browser.execute_script("arguments[0].scrollIntoView();", gotofix)
            break
        except NoSuchElementException:
            browser.execute_script("window.scrollTo(0,document.body.scrollHeight)")
            continue
    # check for new search results and next search result link.
    try:
        WebDriverWait(browser, 3).until(EC.visibility_of_any_elements_located(
            (By.XPATH, "//div[@class='course-list--container--3zXPS']//a[contains(@class,'udlite-custom-focus-visible')]  | //div[@data-purpose='search-course-cards']//a")))
    except TimeoutException:
        nextpage = get_nextpage(browser)
        # end scraper if no new search results and no next search result link
        return df, courses, page_count, nextpage

    courses_links = browser.find_elements_by_xpath(
        "//div[@class='course-list--container--3zXPS']//a[contains(@class,'udlite-custom-focus-visible')] | //div[@data-purpose='search-course-cards']//a")
    links = [c.get_attribute("href") for c in courses_links]
    nextpage = get_nextpage(browser)

    df, courses = scrape_links_navigator(browser, df, cols, courses, links, visited_links)

    return df, courses, page_count, nextpage


def course_scraper(browser, courses, link):
    """

    This checks if minimum requirements are met before scraping all details related to the description of the course.

    """

# =========================Minimum Requirement Check=============================
    try:
        enrolled = WebDriverWait(browser, 3).until(EC.presence_of_element_located((By.XPATH,
                                                                                   """//div[contains(@data-content-group,'Landing Page')]//div[@data-purpose='enrollment'] |
         //div[@class='course-landing-page__main-content']//div[@data-purpose='enrollment']"""))).text.split(" ", 1)[0]
    except TimeoutException:
        print(f"Unable to parse current page. Skipping page :: {link}")
        return False, courses
    else:
        try:
            num_of_reviews = browser.find_element_by_xpath(
                """//div[contains(@data-content-group,'Landing Page')]//div[@class='rate-count'] |
                //div[@class='course-landing-page__main-content']//div[@data-purpose='rating']""").text
        except NoSuchElementException:
            return False, courses
        language = browser.find_element_by_xpath(
            """//div[contains(@data-content-group,'Landing Page')]//div[@class='clp-lead__locale'] |
            //div[@class='course-landing-page__main-content']//div[contains(@class,'clp-lead__locale')]""").text

    if '\n' in num_of_reviews:
        num_of_reviews = num_of_reviews.split('\n')[-1].split()[0][1:]
        page_format = 'revised'
    else:
        num_of_reviews = num_of_reviews.split()[1][1:]
        page_format = 'original'
    # check if students enrolled, number of reviews and language requirements are met
    if int(enrolled.replace(",", "")) < 500 or int(num_of_reviews.replace(",", "")) < 50 or language != "English":
        return False, courses  # skip scraping if not
# ===============================Scrape Page=====================================
    if page_format == 'original':
        proceed, courses = scrape_original(browser, courses, link)
    else:
        proceed, courses = scrape_revised(browser, courses, link)

    return proceed, courses


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
        toggle = WebDriverWait(browser, 3).until(
            EC.visibility_of_element_located((By.XPATH, path)))
        browser.execute_script("arguments[0].click();", toggle)
    except TimeoutException:
        pass


def get_bio_stats_original(browser):
    """

    locate and capture instructor bio and stats information from original page format

    """

    see_more_bio = browser.find_elements_by_xpath(
        "//button[contains(@class,'instructor--view-more-wrapper__button--2egB6')]")
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


def get_bio_stats_revised(browser):
    """

    locate and capture instructor bio and stats information from revised page format

    """

    see_more_bio = browser.find_elements_by_xpath(
        "//div[@class='styles--instructors--2JsS3']//label")
    for s in see_more_bio:
        try:
            s.click()
        except ElementClickInterceptedException:
            browser.execute_script("arguments[0].click();", s)

    bio = browser.find_elements_by_xpath(
        "//div[@data-purpose='description-content']//p")
    instructor_bio = '\n'.join([b.text.strip() for b in bio])

    stats = browser.find_elements_by_xpath(
        "//div[@class='instructor--instructor__image-and-stats--1IqE7']//li")
    stats = [s.text for s in stats]

    return instructor_bio, stats


def expose_filter_menu(browser, filter_by):
    """

    find the text of the label that matches with what is provided and attempt to expose the menu

    """

    exposemenu = browser.find_elements_by_xpath(
        "//label[contains(@class,'js-panel-toggler  panel--label--qoWJs') and @aria-expanded='false']")
    ind = [fltr.text for fltr in exposemenu].index(filter_by)
    browser.execute_script("arguments[0].click();", exposemenu[ind])


def overlay_filter_add(browser, filter_category):
    """

    This adds filter to narrow down the search results using the filter_category provided.
    It also adds a filter to limit the language of the courses to English.

    """
    print('Filtering search results...')
    # attempt to expose all available selections in the Topic section
    while True:
        try:
            expandtopic = browser.find_element_by_xpath(
                "//fieldset[@class='filter--filter-container--1ftIU' and @name='Topic']//button")
            browser.execute_script("arguments[0].click();", expandtopic)
        except NoSuchElementException:
            break
    # find the checkbox that match the filter category and attempt to mark it
    filtercat = browser.find_elements_by_xpath(
        "//fieldset[@class='filter--filter-container--1ftIU' and @name='Topic']//span[@class='filter-option--checkbox-content--4HaUs']")
    try:
        indc = [filter_category in cat.text for cat in filtercat].index(True)
    except ValueError:
        print("Encountered a problem while filtering search results. Unable to filter by the category given.")
        browser.quit()
    checkbox = browser.find_elements_by_xpath(
        "//fieldset[@class='filter--filter-container--1ftIU' and @name='Topic']//input")[indc]
    browser.execute_script("arguments[0].click();", checkbox)

    time.sleep(2)
    # attempt to mark the English language checkbox
    filterlang = browser.find_elements_by_xpath(
        "//fieldset[@class='filter--filter-container--1ftIU' and @name='Language']//span[@class='filter-option--checkbox-content--4HaUs']")
    indl = ['English' in lang.text for lang in filterlang].index(True)
    checkbox = browser.find_elements_by_xpath(
        "//fieldset[@class='filter--filter-container--1ftIU' and @name='Language']//input")[indl]
    browser.execute_script("arguments[0].click();", checkbox)

    time.sleep(1)
    while True:
        try:
            confirm_changes = browser.find_element_by_xpath("//button[contains(text(),'Done')]")
            browser.execute_script("arguments[0].click();", confirm_changes)
        except NoSuchElementException:
            break


def scrape_original(browser, courses, link):
    """

    This scrapes course information from original page format

    """

    course = dict()
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
    while True:
        try:
            course['number_of_lectures'] = browser.find_element_by_xpath(
                "//span[@class='dib']").text
            course['total_video_duration'] = browser.find_element_by_xpath(
                "//span[@class='curriculum-header-length']").text
            break
        except NoSuchElementException:
            return False, courses
        except StaleElementReferenceException:
            time.sleep(1)
            continue
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
            time.sleep(1)
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
        course['instructor_bio'], stats = get_bio_stats_original(browser)
        # create a list of different instructors for each stat
        course['group_instructor_rating'] = stats[::4]
        course['group_reviews'] = stats[1::4]
        course['group_students'] = stats[2::4]
        course['group_courses'] = stats[3::4]

    else:
        course['instructor_name'] = instructors[0].find_element_by_class_name(
            "instructor--title__link--1NJ6S").text
        course['instructor_bio'], stats = get_bio_stats_original(browser)
        course['instructor_rating'], course['total_reviews'], course['total_students'], course['total_courses'] = stats[0], stats[1], stats[2], stats[3]

    courses.append(course)
    return True, courses


def scrape_revised(browser, courses, link):
    """

    This scrapes course information from revised page format

    """

    course = dict()
    course['link'] = link
    course['title'] = browser.find_element_by_xpath("//h1").text
    # expand topic section if it is possible and capture info
    expand_section(
        browser, "//div[@class='what-you-will-learn--what-will-you-learn--mnJ5T']//label')]")
    topics = browser.find_elements_by_class_name("what-you-will-learn--objectives-list--2cWZN")
    course['topics'] = ', '.join([t.text for t in topics])
    # expand course description section if it is possible and capture info
    expand_section(
        browser, "//div[contains(@class,'styles--description--3y4KY')]//label")
    summary = browser.find_elements_by_xpath(
        "//div[@data-purpose='safely-set-inner-html:description:description']//p")
    course['summary'] = '\n'.join([s.text for s in summary[:-3]])
    while True:
        try:
            course['number_of_lectures'] = browser.find_element_by_xpath(
                "//div[@data-purpose='curriculum-stats']").text.split(' • ')[1]
            course['total_video_duration'] = browser.find_element_by_xpath(
                "//div[@data-purpose='curriculum-stats']").text.split(' • ')[2][:-12]
            break
        except NoSuchElementException:
            return False, courses
        except StaleElementReferenceException:
            time.sleep(1)
            continue
    # expand course lectures if it is possible
    expand_toggle(
        browser, '//button[contains(@class,"curriculum--show-more--2tshH")]')
    expand_toggle(browser, '//button[@data-purpose="expand-toggle"]')
    titles = browser.find_elements_by_xpath(
        "//div[@class='section--lecture-title-and-description--3lul7']")
    duration = browser.find_elements_by_xpath(
        "//span[@class='section--lecture-content--2I4Bi']")
    # attempt to capture lecture titles and durations; if encountered a change of the DOM, wait 2 seconds
    while True:
        try:
            course['lectures_breakdown'] = list(
                zip([t.text for t in titles], [d.text for d in duration]))
        except StaleElementReferenceException:
            time.sleep(1)
            continue
        break

    course['original_price'] = browser.find_element_by_xpath(
        "//div[contains(@class,'course-landing-page__purchase-section__main')]//div[@data-purpose='original-price-container']//s/span").text
    # find out if there is one or more instructors information and process them separately
    instructors = browser.find_elements_by_class_name("styles--instructors--2JsS3")
    if len(instructors) > 1:
        # add '-&-' between the names of instructors
        course['instructor_name'] = ' -&- '.join([i.find_element_by_class_name(
            "instructor--instructor__title--34ItB").text for i in instructors])
        course['instructor_bio'], stats = get_bio_stats_revised(browser)
        # create a list of different instructors for each stat
        course['group_instructor_rating'] = stats[::4]
        course['group_reviews'] = stats[1::4]
        course['group_students'] = stats[2::4]
        course['group_courses'] = stats[3::4]

    else:
        course['instructor_name'] = instructors[0].find_element_by_class_name(
            "instructor--instructor__title--34ItB").text
        course['instructor_bio'], stats = get_bio_stats_revised(browser)
        course['instructor_rating'], course['total_reviews'], course['total_students'], course['total_courses'] = stats[0], stats[1], stats[2], stats[3]

    courses.append(course)
    return True, courses
