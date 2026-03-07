#!/usr/bin/env sh
set -eu

api="${1:-joke}"
p1="${2:-}"
p2="${3:-}"

fetch_url() {
  url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -sS "${url}"
  else
    wget -qO- "${url}"
  fi
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
  *)
    echo "{\"error\":\"unsupported_api\",\"api\":\"${api}\",\"supported\":[\"joke\",\"catfact\",\"dogimage\",\"agify\",\"genderize\",\"nationalize\",\"university\",\"openlibrary\",\"randomuser\",\"coingecko\",\"frankfurter\",\"spacex_latest\",\"github_status\",\"hn_topstories\"]}"
    ;;
esac
