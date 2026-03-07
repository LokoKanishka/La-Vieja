#!/usr/bin/env sh
set -eu

api="${1:-joke}"
p1="${2:-}"
p2="${3:-}"

fetch_url() {
  url="$1"
  out=""

  if command -v curl >/dev/null 2>&1; then
    out="$(curl -fsSL "${url}" 2>/dev/null || true)"
  fi

  if [ -z "${out}" ]; then
    out="$(wget -qO- "${url}" 2>/dev/null || true)"
  fi

  if [ -z "${out}" ]; then
    printf '{"error":"fetch_failed","url":"%s"}\n' "${url}"
    return 0
  fi

  printf '%s' "${out}"
}

case "${api}" in
  joke)
    fetch_url "https://v2.jokeapi.dev/joke/Any?type=single"
    ;;
  catfact)
    fetch_url "https://catfact.ninja/fact"
    ;;
  dogimage)
    fetch_url "https://dog.ceo/api/breeds/image/random"
    ;;
  agify)
    name="${p1:-lucy}"
    fetch_url "https://api.agify.io/?name=${name}"
    ;;
  genderize)
    name="${p1:-lucy}"
    fetch_url "https://api.genderize.io/?name=${name}"
    ;;
  nationalize)
    name="${p1:-lucy}"
    fetch_url "https://api.nationalize.io/?name=${name}"
    ;;
  university)
    name="${p1:-technology}"
    fetch_url "http://universities.hipolabs.com/search?name=${name}"
    ;;
  openlibrary)
    title="${p1:-neuromancer}"
    fetch_url "https://openlibrary.org/search.json?title=${title}&limit=5"
    ;;
  randomuser)
    results="${p1:-1}"
    fetch_url "https://randomuser.me/api/?results=${results}"
    ;;
  coingecko)
    coin="${p1:-bitcoin}"
    vs="${p2:-usd}"
    fetch_url "https://api.coingecko.com/api/v3/simple/price?ids=${coin}&vs_currencies=${vs}"
    ;;
  frankfurter)
    from="${p1:-USD}"
    to="${p2:-EUR}"
    fetch_url "https://api.frankfurter.app/latest?from=${from}&to=${to}"
    ;;
  spacex_latest)
    fetch_url "https://api.spacexdata.com/v5/launches/latest"
    ;;
  github_status)
    fetch_url "https://www.githubstatus.com/api/v2/status.json"
    ;;
  hn_topstories)
    fetch_url "https://hacker-news.firebaseio.com/v0/topstories.json"
    ;;
  chucknorris)
    fetch_url "https://api.chucknorris.io/jokes/random"
    ;;
  advice)
    fetch_url "https://api.adviceslip.com/advice"
    ;;
  yesno)
    fetch_url "https://yesno.wtf/api"
    ;;
  deck_draw)
    fetch_url "https://deckofcardsapi.com/api/deck/new/draw/?count=1"
    ;;
  restcountries)
    country="${p1:-argentina}"
    fetch_url "https://restcountries.com/v3.1/name/${country}?fields=name,capital,population,region"
    ;;
  pokeapi)
    pokemon="${p1:-pikachu}"
    fetch_url "https://pokeapi.co/api/v2/pokemon/${pokemon}"
    ;;
  swapi_people)
    person_id="${p1:-1}"
    fetch_url "https://swapi.py4e.com/api/people/${person_id}"
    ;;
  openbrewery)
    city="${p1:-san_diego}"
    fetch_url "https://api.openbrewerydb.org/v1/breweries?per_page=3&by_city=${city}"
    ;;
  dictionary)
    word="${p1:-hello}"
    fetch_url "https://api.dictionaryapi.dev/api/v2/entries/en/${word}"
    ;;
  ipify)
    fetch_url "https://httpbin.org/ip"
    ;;
  worldtime)
    zone="${p1:-Etc/UTC}"
    fetch_url "https://timeapi.io/api/Time/current/zone?timeZone=${zone}"
    ;;
  jsonplaceholder_todo)
    todo_id="${p1:-1}"
    fetch_url "https://jsonplaceholder.typicode.com/todos/${todo_id}"
    ;;
  github_repo)
    repo="${p1:-octocat/Hello-World}"
    fetch_url "https://api.github.com/repos/${repo}"
    ;;
  open_er)
    base="${p1:-USD}"
    fetch_url "https://open.er-api.com/v6/latest/${base}"
    ;;
  jikan_top_anime)
    fetch_url "https://api.jikan.moe/v4/top/anime?limit=3"
    ;;
  *)
    echo "{\"error\":\"unsupported_api\",\"api\":\"${api}\",\"supported\":[\"joke\",\"catfact\",\"dogimage\",\"agify\",\"genderize\",\"nationalize\",\"university\",\"openlibrary\",\"randomuser\",\"coingecko\",\"frankfurter\",\"spacex_latest\",\"github_status\",\"hn_topstories\",\"chucknorris\",\"advice\",\"yesno\",\"deck_draw\",\"restcountries\",\"pokeapi\",\"swapi_people\",\"openbrewery\",\"dictionary\",\"ipify\",\"worldtime\",\"jsonplaceholder_todo\",\"github_repo\",\"open_er\",\"jikan_top_anime\"]}"
    ;;
esac
