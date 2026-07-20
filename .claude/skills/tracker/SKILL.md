---
name: tracker
description: |
  Обходит фиксированный список URL интернет-магазинов, для каждого получает цену товара через уже готовый скилл extract-price и собирает результат в единую таблицу прогона (одна строка на товар). Используй, когда нужно отследить/сравнить цену конкретного товара (Premier, ягнёнок с индейкой для собак средних пород, 10 кг) по списку ниже.

  Список URL для обхода:
  https://petsmart.ru/product/10152-premier-adult-medium-korm-s-yagnenkom-i-indejkoj-dlya-sobak-srednix-porod-10-kg
  https://zoozavr.ru/product/index/id/6189303/
  https://kotmatros.ru/premier-dog-lamb-turkey-adult-medium-suhoj-korm-dlya-sobak-srednih-porod-svezhee-myaso-yagnenka-s-indejkoj-10-kg/
  https://glavnoehvost.ru/katalog/sobaki/korma-dla-sobak/suhie-korma/premier-dla-sobak-adult-medium-agnenok-indejka/9196
  https://www.zoogastronom.ru/product/suhoy-korm-premier-yagnenok-s-indeykoy-dlya-sobak-srednih-porod
  https://katiko.ru/premier-yagnenka-indejkoj-sobak-krupnyh-10
  https://www.dogeat.ru/catalog/korm/dlya-sobak/premier/
  https://premier.pet/catalog/dog_foods/medium_breeds/pr_adult_medium_lamb_turkey_1_kg/
  https://multikorm.ru/category/sobaki/korma-dlya-sobak/sukhoy-korm-dlya-sobak/premier-sukhoy-korm-dlya-sobak/premier-sukhoy-korm-dlya-sobak-10-kg/
---

# Tracker

Прогоняет фиксированный список URL (см. `description` выше) и собирает по ним единую таблицу цен. Не дублирует логику извлечения цены — на каждом URL переиспользует уже готовый skill `extract-price` (раздел «Порядок действий: URL страницы»).

## Список URL для обхода

1. https://petsmart.ru/product/10152-premier-adult-medium-korm-s-yagnenkom-i-indejkoj-dlya-sobak-srednix-porod-10-kg
2. https://zoozavr.ru/product/index/id/6189303/
3. https://kotmatros.ru/premier-dog-lamb-turkey-adult-medium-suhoj-korm-dlya-sobak-srednih-porod-svezhee-myaso-yagnenka-s-indejkoj-10-kg/
4. https://glavnoehvost.ru/katalog/sobaki/korma-dla-sobak/suhie-korma/premier-dla-sobak-adult-medium-agnenok-indejka/9196
5. https://www.zoogastronom.ru/product/suhoy-korm-premier-yagnenok-s-indeykoy-dlya-sobak-srednih-porod
6. https://katiko.ru/premier-yagnenka-indejkoj-sobak-krupnyh-10
7. https://www.dogeat.ru/catalog/korm/dlya-sobak/premier/
8. https://premier.pet/catalog/dog_foods/medium_breeds/pr_adult_medium_lamb_turkey_1_kg/
9. https://multikorm.ru/category/sobaki/korma-dlya-sobak/sukhoy-korm-dlya-sobak/premier-sukhoy-korm-dlya-sobak/premier-sukhoy-korm-dlya-sobak-10-kg/

## Порядок действий

1. Взять список URL выше (не искать и не подбирать источники самостоятельно — список фиксированный).
2. Для каждого URL по очереди вызвать skill `extract-price`, раздел «Порядок действий: URL страницы» (WebFetch страницы → общая логика извлечения цены из `extract-price` → объект `{ regular_price, sale_price }`, либо `товар не найден` с причиной — блокировка, страница не парсится, JS-заглушка, товара нет в наличии и т.п.).
3. Не переопределять и не копировать логику парсинга цены внутри `tracker` — вся эта логика берётся из `extract-price` как есть.
4. Собрать результаты всех URL в одну таблицу прогона, по одной строке на товар/магазин:

   | Магазин (домен) | URL | regular_price | sale_price | Статус |
   |---|---|---|---|---|
   | petsmart.ru | https://petsmart.ru/... | 8260.90 | null | ok |
   | glavnoehvost.ru | https://glavnoehvost.ru/... | — | — | не удалось получить цену (JS, цена не отображается в ответе) |

   - «Магазин» — домен из URL.
   - `regular_price` / `sale_price` — значения из объекта, который вернул `extract-price` (или прочерк, если `товар не найден`).
   - «Статус» — `ok`, либо краткая причина неудачи (без выдумывания цены вместо неё).
5. После таблицы — коротко отметить минимальную цену среди строк со статусом `ok` (по общей логике `extract-price`: сравнивать `sale_price`, если он есть, иначе `regular_price`).
