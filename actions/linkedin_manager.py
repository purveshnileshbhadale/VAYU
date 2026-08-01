import webbrowser
from urllib.parse import quote_plus


def linkedin_manager(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "").strip().lower().replace(" ", "_")

    if player:
        player.write_log(f"[LinkedIn] action={action}")

    try:
        if action in ("search_job", "jobs", "job_search"):
            title = params.get("title", "").strip()
            location = params.get("location", "").strip()

            if not title:
                return "Job title is required for job search."

            return _search_jobs(title, location)

        elif action in ("search_people", "people", "profile_search"):
            name = params.get("name", "").strip()
            keyword = params.get("keyword", "").strip()

            if not name and not keyword:
                return "Person name or keyword is required."

            return _search_people(name, keyword)

        elif action in ("search_company", "company"):
            company = params.get("company", "").strip()
            if not company:
                return "Company name is required."
            return _search_company(company)

        elif action in ("my_profile", "profile", "view_profile"):
            return _my_profile()

        elif action in ("network", "connections"):
            return _network()

        elif action in ("messaging", "messages", "inbox"):
            return _messaging()

        elif action in ("notifications", "alerts"):
            return _notifications()

        elif action in ("post", "create_post"):
            content = params.get("content", "").strip()
            return _create_post(content)

        elif action in ("saved_jobs", "saved"):
            return _saved_jobs()

        elif action in ("analytics", "dashboard"):
            return _analytics()

        return (
            f"Unknown action: '{action}'. "
            f"Available: search_job, search_people, search_company, my_profile, "
            f"network, messaging, notifications, post, saved_jobs, analytics"
        )

    except Exception as e:
        return f"LinkedIn manager failed: {e}"


def _search_jobs(title: str, location: str) -> str:
    params = f"keywords={quote_plus(title)}"
    if location:
        params += f"&location={quote_plus(location)}"

    url = f"https://www.linkedin.com/jobs/search/?{params}"
    webbrowser.open(url)

    msg = f"Opened LinkedIn job search for '{title}'"
    if location:
        msg += f" in {location}"
    msg += "."
    return msg


def _search_people(name: str, keyword: str) -> str:
    query = name or keyword
    url = f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(query)}"
    webbrowser.open(url)

    msg = f"Opened LinkedIn people search for '{query}'."
    return msg


def _search_company(company: str) -> str:
    url = f"https://www.linkedin.com/search/results/companies/?keywords={quote_plus(company)}"
    webbrowser.open(url)

    return f"Opened LinkedIn company search for '{company}'."


def _my_profile() -> str:
    webbrowser.open("https://www.linkedin.com/in/")
    return "Opened your LinkedIn profile. Make sure you're logged in."


def _network() -> str:
    webbrowser.open("https://www.linkedin.com/mynetwork/")
    return "Opened your LinkedIn network — see connection requests, suggestions, and manage your network."


def _messaging() -> str:
    webbrowser.open("https://www.linkedin.com/messaging/")
    return "Opened LinkedIn messaging inbox."


def _notifications() -> str:
    webbrowser.open("https://www.linkedin.com/notifications/")
    return "Opened LinkedIn notifications."


def _create_post(content: str) -> str:
    webbrowser.open("https://www.linkedin.com/post/new/")
    msg = "Opened LinkedIn post composer."
    if content:
        msg += f" Draft content: '{content[:200]}'"
    return msg


def _saved_jobs() -> str:
    webbrowser.open("https://www.linkedin.com/my-items/saved-jobs/")
    return "Opened your saved jobs on LinkedIn."


def _analytics() -> str:
    webbrowser.open("https://www.linkedin.com/analytics/")
    return "Opened LinkedIn analytics dashboard."
