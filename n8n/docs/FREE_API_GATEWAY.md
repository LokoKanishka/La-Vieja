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

Ejemplos:

- `...?api=joke`
- `...?api=catfact`
- `...?api=agify&p1=lucy`
- `...?api=coingecko&p1=bitcoin&p2=usd`
- `...?api=restcountries&p1=argentina`
- `...?api=worldtime&p1=Etc/UTC`
- `...?api=github_repo&p1=openai/openai-cookbook`
