# Free API Gateway (Sin Tarjeta)

Webhook base:

- `GET /webhook/<id>/webhook-free-api-gateway/api/free/gateway`

Parametros:

- `api` (obligatorio logico, default `joke`)
- `p1` (opcional)
- `p2` (opcional)

APIs disponibles hoy:

- `joke`
- `catfact`
- `dogimage`
- `agify` (`p1=name`)
- `genderize` (`p1=name`)
- `nationalize` (`p1=name`)
- `university` (`p1=keyword`)
- `openlibrary` (`p1=title`)
- `randomuser` (`p1=results`)
- `coingecko` (`p1=coin`, `p2=vs_currency`)
- `frankfurter` (`p1=from`, `p2=to`)
- `spacex_latest`
- `github_status`
- `hn_topstories`
- `chucknorris`
- `advice`
- `yesno`
- `deck_draw`
- `restcountries` (`p1=country`)
- `pokeapi` (`p1=pokemon`)
- `swapi_people` (`p1=id`)
- `openbrewery` (`p1=city`)
- `dictionary` (`p1=word`)
- `ipify` (fuente: `httpbin /ip`)
- `worldtime` (`p1=zone`, ejemplo `Etc/UTC`, fuente: `timeapi.io`)
- `jsonplaceholder_todo` (`p1=id`)
- `github_repo` (`p1=owner/repo`)
- `open_er` (`p1=base_currency`)
- `jikan_top_anime`
- `kanye`
- `official_joke`
- `randomfox`
- `meowfacts`
- `mempool_fees`
- `ipapi_is`
- `nager_holidays` (`p1=year`, `p2=country`)
- `sunrise_sunset` (`p1=lat`, `p2=lon`)
- `tvmaze_search` (`p1=query`)
- `opentdb`
- `artic_artworks`
- `openf1_drivers`
- `random_word`
- `bible_verse` (`p1=verse`, ejemplo `john+3:16`)
- `github_zen`
- `httpbin_uuid`
- `sample_coffee`
- `nhtsa_makes`
- `nasa_apod`
- `openalex` (`p1=query`)

Ejemplos:

- `...?api=joke`
- `...?api=catfact`
- `...?api=agify&p1=lucy`
- `...?api=coingecko&p1=bitcoin&p2=usd`
- `...?api=restcountries&p1=argentina`
- `...?api=worldtime&p1=Etc/UTC`
- `...?api=github_repo&p1=openai/openai-cookbook`
- `...?api=nager_holidays&p1=2026&p2=US`
- `...?api=sunrise_sunset&p1=-34.6037&p2=-58.3816`
- `...?api=openalex&p1=robotics`
