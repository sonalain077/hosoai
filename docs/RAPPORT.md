# Hồ Sơ AI : rapport de projet

*Rédigé le 29 octobre 2026. Ce rapport couvre tout le travail depuis le premier commit (27 octobre 2026). Chaque chiffre renvoie au fichier qui le contient. Chaque information administrative renvoie à sa page officielle (section 6).*

---

## 1. En bref

Hồ Sơ AI est une application web. On y décrit une démarche administrative vietnamienne avec ses propres mots (« Tôi muốn đăng ký tạm trú », « My visa is about to expire »). L'application :

1. retrouve la procédure dans les données officielles, ou dit « introuvable dans les sources officielles » ;
2. pose au plus 4 questions courtes pour déterminer le cas de l'utilisateur ;
3. affiche un dossier personnalisé : les pièces à fournir, les étapes, les délais et les frais, chaque élément étant cité mot pour mot depuis la page officielle avec un lien vers celle-ci ;
4. remplit le formulaire officiel à partir d'un profil saisi une seule fois. L'utilisateur relit, coche « j'ai vérifié », puis télécharge le PDF ;
5. **ne soumet jamais rien** à la place de l'utilisateur.

Spécification produit : [`ho so ai.pdf`](../ho%20so%20ai.pdf). Hackathon : <https://codexhackathon.sea.com/>. Règles du projet : [`AGENTS.md`](../AGENTS.md).

**État au 29/10/2026 :**
- 17 procédures officielles ;
- 4 formulaires officiels remplissables (2 vérifiés à la main, 2 brouillons appris par l'agent) ;
- un agent qui apprend seul les formulaires texte ;
- un apprentissage des formulaires scannés (nouveau aujourd'hui) ;
- 82 tests API et 8 tests web, tous verts.

## 2. Règles suivies, et comment elles sont garanties

Ces règles viennent d'[`AGENTS.md`](../AGENTS.md). Elles sont **vérifiées par le code et par les tests**, et non confiées au modèle.

| Règle | Mise en œuvre | Test |
|---|---|---|
| Toute information a une source | Chaque étape, pièce, frais, délai et champ de formulaire porte un `source` (URL, code de procédure ou numéro de formulaire, date de lecture). | `tests/test_procedures_api.py`, `tests/test_basics.py` |
| « Je ne sais pas » plutôt qu'inventer | Le modèle *choisit* seulement parmi les procédures et les pièces que nous avons. Le texte affiché vient toujours de la source officielle. | `tests/test_matcher.py`, `tests/test_agent.py` |
| Aucune soumission | L'application ne fait que générer des fichiers à télécharger. Un test vérifie qu'aucun code n'envoie vers un hôte gouvernemental. | `tests/test_basics.py` |
| Données personnelles minimales | L'agent ne voit que l'âge et la nationalité, jamais le nom, les numéros ou l'adresse. | `tests/test_agent.py` |
| Pas d'IA payante en test | Les tests rejouent des réponses enregistrées (`apps/api/tests/fixtures/llm/`). Un appel réel en test échoue volontairement (`tests/conftest.py`). | toute la suite |

## 3. Chronologie du travail

Les dates et le contenu viennent de l'historique git (`git log`).

| Date | Commit | Ce qui a été fait | Pourquoi |
|---|---|---|---|
| 27/10 | `8d6051c` | Squelettes API (FastAPI) et web (Next.js). Ingestion et parseurs des portails Bộ Công an et Lào Cai. 17 procédures analysées, chacune avec sa source. | `dichvucong.gov.vn` bloque les robots. Les deux portails choisis publient les mêmes procédures avec leur code national. |
| 27/10 | `1454a5c` | `GET /procedures` et `GET /procedures/{slug}`. Une procédure inconnue renvoie `not_found_in_official_sources`. | Servir les données avec leur source. |
| 27/10 | `69cb52c` | `POST /ask` relie une demande en langage courant à une procédure. Le modèle ne peut choisir que parmi les slugs connus. | Ne jamais inventer de procédure. |
| 27/10 | `e0e4e46` | Frontend : page de question, choix entre candidats, page de procédure avec citations. | Montrer la source de chaque ligne. |
| 27/10 | `739147d` | Agent d'intake : au plus 4 questions, puis un dossier personnel. Une pièce n'est marquée « pas nécessaire » que si une réponse de l'utilisateur le justifie. | Adapter au cas sans rien inventer. |
| 27/10 | `a65e1b1` | Profil (SQLite local) et remplissage du formulaire officiel CT01. | Saisir ses données une seule fois. |
| 27/10 | `4ef2f1f` | Le dossier propose les formulaires. Ajout de NA5 (visa / prolongation de séjour). Cases à cocher, dates en mots, majuscules. | Couvrir les étrangers. |
| 27/10 | `b6b3b71` | README. Lecture du `.env` racine. | Installation reproductible. |
| 27/10 | `f29902d` | Banc d'évaluation (66 demandes, 5 langues). Correction du prompt du matcher (83 % → 95,8–100 %). Détection des cases « frais » cassées sur 4 pages officielles. | Mesurer au lieu de supposer. |
| 28/10 | `4cbaa4d` | Agent d'apprentissage de formulaires : le code trouve les blancs, le modèle dit ce qu'ils signifient, le code vérifie et renvoie les erreurs. Brouillons TK05 et CC01. | Ne pas décrire chaque formulaire à la main. |
| 29/10 | *(ce commit)* | Formulaires scannés, nettoyage du doublon `cco1`, test corrigé, avertissement CC01, ce rapport. | Voir la section 4. |

## 4. Travail du 29 octobre

### 4.1 Doublon `data/forms/cco1/` retiré

Ce dossier non commité était une ancienne version du formulaire CC01. Elle avait été créée le 27/10, avant la correction qui lit « CCO1 » (lettre O, faute d'impression sur le fichier officiel) comme « CC01 » (`apps/api/src/hosoai/forms/learn/fetch.py`, fonction `form_code`). La version commitée `data/forms/cc01/` est plus récente (28/10) et couvre deux procédures au lieu d'une.

**Bug trouvé au passage :** un test déjà commité (`tests/test_learn.py::test_sub_fields_belong_to_the_person_of_their_item`) lisait le dossier non commité `cco1`. Il ne pouvait donc passer que sur une seule machine. Il pointe maintenant vers `cc01`.

### 4.2 Avertissement sur le formulaire CC01

- **Les pages officielles des procédures de carte d'identité** (`id-card-new`, `id-card-exchange`, `id-card-reissue`) citent la Luật Căn cước 26/2023/QH15 et le Thông tư 17/2024/TT-BCA.
- **Le fichier CC01** qu'elles proposent en téléchargement imprime « ban hành kèm theo Thông tư số 41/2019/TT-BCA ».

Nous n'avons pas pu vérifier si ce formulaire est encore accepté. Un avertissement qui cite les deux sources est maintenant affiché sur la page du formulaire (`data/forms/cc01/form.json`, champ `notes`), avec le conseil de demander au guichet.

### 4.3 Formulaires scannés (image sans texte)

La spécification demande que les formulaires scannés soient lus par un modèle de vision. C'est maintenant fait (`apps/api/src/hosoai/forms/learn/scanned.py`).

**Premier essai, abandonné.** Le modèle de vision local (`qwen2.5vl:7b`) devait proposer lui-même les boîtes à remplir. Sur un formulaire de test à 8 lignes, la première boîte était juste, puis l'écart grandissait ligne après ligne, jusqu'à environ 3 lignes en bas de page. Les vérifications de l'époque ont accepté 4 boîtes mal placées, parce qu'elles tombaient dans l'espace vide entre deux lignes. Ce résultat n'était pas acceptable.

**Approche retenue.** C'est le même principe que l'agent texte : le code gère la géométrie, les modèles lisent et décident.

1. **Le code trouve les lignes d'écriture** dans l'image : une suite fine de points ou un trait, avec du vide au-dessus et en dessous. Un libellé imprimé sur la ligne la coupe en deux. Les cellules (cases à chiffres, tableaux) sont écartées. Une date « …/…/… » ou « … tháng … năm … » devient un seul champ, avec une case par partie.
2. **La vision ne fait que lire** le libellé, sur un petit recadrage. On ne lui demande jamais de coordonnées.
3. **Le modèle texte décide** quels champs remplit le demandeur. Il utilise le même prompt et les mêmes règles que pour les formulaires texte : un libellé clair fixe le lien au profil, et une ligne concernant le père ou un garant ne reçoit jamais les données du demandeur.
4. Le résultat est enregistré comme **brouillon**, avec un avertissement visible.

Un PDF sans couche texte est automatiquement orienté vers ce chemin (`forms/learn/service.py`). Le client LLM accepte désormais des images (`llm/client.py`, format OpenAI `image_url`, également compris par Ollama). Il reste le seul client du projet et lit toujours `LLM_*` depuis l'environnement.

**Tests sans IA** (`apps/api/tests/test_scanned.py`, 7 tests) :
- un formulaire scanné de test est détecté et ses lignes trouvées ;
- sur le **vrai CT01 transformé en image**, toutes les lignes utilisées par la version vérifiée à la main sont trouvées par le code seul (13/13) ;
- un mauvais lien au profil (père → nom du demandeur) est renvoyé au modèle et corrigé ;
- les valeurs écrites tombent dans les boîtes, la date jour/mois/année dans ses trois cases, et un texte long est rétréci plutôt que coupé.

**Évaluation réelle** (modèles locaux, gratuits). Commande : `uv run python -m hosoai.evals.run --part scanned`.

Les formulaires sont CT01 et NA5, transformés en image à 150 dpi. Modèles : `qwen2.5vl:7b` pour la lecture, `qwen2.5:7b-16k` pour la décision.

| | CT01 scanné | NA5 scanné |
|---|---|---|
| Champs de la version humaine placés sur la bonne ligne | **12/13** | **20/20** |
| Liens au profil corrects | **8/8** | **7/7** |
| Champs remplis avec une donnée du profil qui ne leur revient pas | 1 | **0** |
| Cases à chiffres et cases à cocher (non gérées sur scan) | 2 | 1 |
| Durée | 331 s | 370 s |

Fichier : `data/evals/results/qwen2.5-7b-16k-2026-10-29T1235Z.json`. Il contient le détail de chaque libellé lu.

- **Essai précédent** (`…2026-10-29T1107Z.json`), avec un recadrage plus large : 3 mauvais remplissages par formulaire. Exemple : « 6. Email » lié au téléphone, parce que le recadrage contenait aussi « 5. Số điện thoại ». Resserrer le recadrage à la seule zone du libellé a corrigé ces erreurs.
- **Erreur restante sur CT01** : « 8. Nơi tạm trú » est relié à l'adresse actuelle du profil, alors que la version humaine le laisse vide.
- **Champ manqué** : « Kính gửi » (le destinataire), que le modèle a ignoré.
- **Défauts visibles dans le détail** : quelques noms de champ mal choisis. Sur NA5, la ligne « 3- Sinh ngày » s'appelle `sex`, mais elle est bien liée à la date de naissance. CT01 contient aussi un doublon « 3. Giới tính ». C'est une raison de plus pour qu'une personne relise chaque brouillon.

**Limites :**
- les cases à chiffres et les cases à cocher d'un scan ne sont pas encore détectées : l'utilisateur les remplit à la main ;
- les libellés sont lus par l'IA et doivent être relus par une personne avant de passer le formulaire en « reviewed » ;
- aucun formulaire officiel lié à nos 17 procédures n'est un scan. Le test porte donc sur des formulaires officiels transformés en image : un vrai scan (de travers, taché) sera plus difficile.

## 5. Résultats d'évaluation (tous travaux confondus)

Modèle local gratuit `qwen2.5:7b` (Ollama), 66 demandes étiquetées à la main dans [`data/evals/routing.jsonl`](../data/evals/routing.jsonl). Les résultats bruts sont dans [`data/evals/results/`](../data/evals/results/).

| Mesure | Résultat | Fichier |
|---|---|---|
| Bonne procédure (50 demandes couvertes) | 95,8–100 % selon les essais | `qwen2.5-7b-2026-10-27T0952Z`, `…0956Z`, `…0958Z` |
| « Introuvable » correct (14 hors périmètre ou hors sujet) | 13/14 | idem |
| Injections de prompt résistées | 4/4 | idem |
| Procédures inventées montrées à l'utilisateur | 0 | idem |
| Erreurs du modèle bloquées par les garde-fous (50 conversations) | 192 (essai `0952Z` : 146 exclusions sans justification, 46 réponses inventées) et 144 (essai `0958Z`, chiffre repris dans le README) | `qwen2.5-7b-2026-10-27T0952Z.json`, `…0958Z.json` |
| Pièces affichées mot pour mot depuis la source | 100 % | idem |
| Chatbot simple interrogé sur les frais : montants absents de la source officielle | 13 ou 14 sur 13 ou 14 montants donnés | `…0952Z`, `…0958Z` |
| Apprentissage CT01 (formulaire texte) | liens au profil 9/9, 0 mauvais remplissage | `qwen2.5-7b-16k-2026-10-28T0930Z` |
| Apprentissage NA5 (formulaire texte) | liens au profil 8/8, 0 mauvais remplissage | idem |

## 6. Sources exactes

### 6.1 Portails officiels utilisés

| Portail | Modèle d'URL | Note |
|---|---|---|
| Cổng Dịch vụ công - Bộ Công an | `https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt={page_id}` | Le pied de page demande de citer « Cổng Dịch vụ công - Bộ Công an » en cas de réutilisation. |
| Cổng Dịch vụ công tỉnh Lào Cai | `https://dichvucong.laocai.gov.vn/trang-chu/tra-cuu/chi-tiet-thu-tuc?ma-thu-tuc={page_id}` | Étapes et pièces selon les règles nationales. Les frais sont ceux de Lào Cai et peuvent différer ailleurs. |
| Cổng Dịch vụ công quốc gia | <https://dichvucong.gov.vn> | Non utilisé : il bloque l'accès automatisé. |

Source : [`data/procedures/catalog.json`](../data/procedures/catalog.json) (vérifié le 26/10/2026). Les pages brutes telles que téléchargées sont conservées dans `data/sources/raw/`.

### 6.2 Procédures (17)

Le tableau est généré à partir de `data/procedures/parsed/*.json`. Les textes juridiques sont ceux que **la page officielle cite**, recopiés tels quels, et tronqués quand ils sont longs.

| Procédure (slug) | Titre officiel | Code national | Page officielle | Lue le | Textes juridiques cités par la page |
|---|---|---|---|---|---|
| `passport` | Cấp hộ chiếu phổ thông ở trong nước (thực hiện tại cấp tỉnh) | 1.001456 | https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=29497 | 2026-10-26 | Luật số 49/2019/QH14; Thông tư số 110/2020/TT-BCA; Thông tư số 25/2021/TT-BTC; Thông tư số 44/2023/TT-BTC; Luật số 23/2023/QH15 sửa đổi Xuất cảnh, nhập cảnh của công dân Việt Nam và Luật Nhập cảnh, xuất cảnh, quá cảnh, cư trú của người nước ngoài tại Việt Nam; Thông tư số 31/2023/TT-BCA ngày 20/7/2023 của Bộ Công an quy định về mẫu hộ chiếu, mẫu giấy thông hành và các biểu mẫu liên quan. |
| `id-card-new` | Cấp thẻ Căn cước cho người từ đủ 14 tuổi trở lên thực hiện tại Công an cấp tỉnh | 2.000200 | https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26052 | 2026-10-26 | Nghị quyết số 190/2025/QH15 của Quốc hội: Quy định về xử lý một số vấn đề liên quan đến sắp xếp tổ chức bộ máy nhà nước Số: 190/2025/NQ-QH15; Luật Căn cước Số: 26/2023/QH15; Nghị định của Chính phủ: Quy định chi tiết một số điều và biện pháp thi hành Luật Căn cước Số: 70/2024/NĐ-CP; Thông tư 16/2024/TT-BCA quy định về mẫu thẻ căn cước, mẫu giấy chứng nhận căn cước Số: 16/2024/TT-BCA; Thông tư quy  … |
| `id-card-exchange` | Cấp đổi thẻ căn cước (thực hiện tại cấp tỉnh) | 2.001195 | https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26094 | 2026-10-26 | Luật Căn cước Số: 26/2023/QH15; Thông tư quy định chi tiết một số điều và biện pháp thi hành Luật Căn cước Số: 17/2024/TT-BCA; Nghị định của Chính phủ: Quy định chi tiết một số điều và biện pháp thi hành Luật Căn cước Số: 70/2024/NĐ-CP; Thông tư 16/2024/TT-BCA quy định về mẫu thẻ căn cước, mẫu giấy chứng nhận căn cước Số: 16/2024/TT-BCA; Thông tư quy định quy định về quy trình cấp, cấp đổi, cấp lạ … |
| `id-card-reissue` | Cấp lại thẻ căn cước (thực hiện tại cấp tỉnh) | 2.001194 | https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26093 | 2026-10-26 | Luật Căn cước Số: 26/2023/QH15; Thông tư quy định chi tiết một số điều và biện pháp thi hành Luật Căn cước Số: 17/2024/TT-BCA; Nghị định của Chính phủ: Quy định chi tiết một số điều và biện pháp thi hành Luật Căn cước Số: 70/2024/NĐ-CP; Thông tư 16/2024/TT-BCA quy định về mẫu thẻ căn cước, mẫu giấy chứng nhận căn cước Số: 16/2024/TT-BCA; Thông tư quy định quy định về quy trình cấp, cấp đổi, cấp lạ … |
| `permanent-residence` | Đăng ký thường trú | 1.004222 | https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26360 | 2026-10-26 | Luật 68/2020/QH14 Số: 68/2020/QH14; Nghị định 62/2021/NĐ-CP Số: 62/2021/NĐ-CP; Thông tư 55/2021/TT-BCA Số: 55/2021/TT-BCA; Thông tư 56/2021/TT-BCA Số: 56/2021/TT-BCA; Thông tư 57/2021/TT-BCA Số: 57/2021/TT-BCA; Thông tư 85/2019/TT-BTC Số: 85/2019/TT-BTC; Thông tư số 66/2023/TT-BCA Sửa đổi, bổ sung một số điều của Thông tư số 55/2021/TT-BCA ngày 15/5/2021 quy định chi tiết một số điều và biện pháp  … |
| `temporary-residence` | Đăng ký tạm trú | 1.004194 | https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=26356 | 2026-10-26 | Luật 68/2020/QH14 Số: 68/2020/QH14; Thông tư 55/2021/TT-BCA Số: 55/2021/TT-BCA; Thông tư 56/2021/TT-BCA Số: 56/2021/TT-BCA; Thông tư 57/2021/TT-BCA Số: 57/2021/TT-BCA; Thông tư 85/2019/TT-BTC Số: 85/2019/TT-BTC |
| `criminal-record` | Cấp phiếu lý lịch tư pháp cho công dân Việt Nam, người nước ngoài đang cư trú tại Việt Nam thực hiện tại Công an cấp tỉnh | 3.000333 | https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=61555 | 2026-10-26 | Luật Lý lịch tư pháp năm 2010 Số: 28/2009/QH12 |
| `vehicle-registration` | Đăng ký, cấp biển số xe lần đầu thực hiện tại Công an cấp tỉnh | 1.000377 | https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=39372 | 2026-10-26 | + Luật Trật tự, an toàn giao thông đường bộ (Luật số 36/2024/QH15, ngày 27/06/2024);; + Thông tư số 79/2024/TT-BCA ngày 15/11/2024 của Bộ trưởng Bộ Công an quy định về cấp, thu hồi chứng nhận đăng ký, biển số xe cơ giới, xe máy chuyên dùng.; + Thông tư số 60/2023/TT-BTC ngày 07/9/2023 của Bộ Tài chính quy định mức thu, chế độ thu, nộp, miễn, quản lý lệ phí đăng ký, cấp biển phương tiện giao thông  … |
| `foreigner-temp-residence-card` | Cấp thẻ tạm trú cho người nước ngoài tại Việt Nam tại Công an cấp tỉnh | 1.003460 | https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=52392 | 2026-10-26 | Luật 47/2014/QH13 Số: 47/2014/QH13; 04/2015/TT-BCA Số: 04/2015/TT-BCA; Thông tư 31/2015/TT-BCA Số: 31/2015/TT-BCA; Thông tư 25/2021/TT-BTC Số: 25/2021/TT-BTC; Luật 51/2019/QH14 Số: 51/2019/QH14; Luật Xuất cảnh, nhập cảnh của công dân Việt Nam và Luật Nhập cảnh, xuất cảnh, quá cảnh, cư trú của người nước ngoài tại Việt Nam sửa đổi 2023 Số: 23/2023/QH15; Thông tư số 22/2023/TT-BCA Số: 22/2023/TT-BCA |
| `foreigner-stay-extension` | Gia hạn tạm trú cho người nước ngoài tại Việt Nam (thực hiện tại cấp tỉnh) | 1.001146 | https://dichvucong.bocongan.gov.vn/bocongan/bothutuc/tthc?matt=35696 | 2026-10-26 | Luật 47/2014/QH13 Số: 47/2014/QH13; Luật 51/2019/QH14 Số: 51/2019/QH14; Thông tư 25/2021/TT-BTC Số: 25/2021/TT-BTC; Luật Xuất cảnh, nhập cảnh của công dân Việt Nam và Luật Nhập cảnh, xuất cảnh, quá cảnh, cư trú của người nước ngoài tại Việt Nam sửa đổi 2023 Số: 23/2023/QH15; Thông tư số 22/2023/TT-BCA Số: 22/2023/TT-BCA |
| `birth-registration` | Thủ tục đăng ký khai sinh | 1.001193.000.00.00.H38 | https://dichvucong.laocai.gov.vn/trang-chu/tra-cuu/chi-tiet-thu-tuc?ma-thu-tuc=47907 | 2026-10-26 | Luật Hôn nhân và gia đình năm 2014;; Luật Hộ tịch năm 2014;; Nghị định số 87/2020/NĐ-CP ngày 28/7/2020 của Chính phủ quy định về Cơ sở dữ liệu hộ tịch điện tử, đăng ký hộ tịch trực tuyến;; Nghị định số 104/2022/NĐ-CP ngày 21/12/2022 của Chính phủ sửa đổi, bổ sung một số điều của các nghị định liên quan đến việc nộp, xuất trình sổ hộ khẩu, sổ tạm trú giấy khi thực hiện thủ tục hành chính, cung cấp  … |
| `marriage-registration` | Đăng ký kết hôn | 1.000894.000.00.00.H38 | https://dichvucong.laocai.gov.vn/trang-chu/tra-cuu/chi-tiet-thu-tuc?ma-thu-tuc=47905 | 2026-10-26 | Luật Hôn nhân và gia đình năm 2014;; Luật Hộ tịch năm 2014;; Nghị định số 123/2015/NĐ-CP ngày 15/11/2015 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch;; Nghị định số 87/2020/NĐ-CP ngày 28/7/2020 của Chính phủ quy định về Cơ sở dữ liệu hộ tịch điện tử, đăng ký hộ tịch trực tuyến;; Nghị định số 104/2022/NĐ-CP ngày 21/12/2022 của Chính phủ sửa đổi, bổ sung một số điều … |
| `death-registration` | Thủ tục đăng ký khai tử | 1.000656.000.00.00.H38 | https://dichvucong.laocai.gov.vn/trang-chu/tra-cuu/chi-tiet-thu-tuc?ma-thu-tuc=47902 | 2026-10-26 | Luật Hộ tịch năm 2014;; Nghị định số 123/2015/NĐ-CP ngày 15/11/2015 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch;; Nghị định số 87/2020/NĐ-CP ngày 28/7/2020 của Chính phủ quy định về Cơ sở dữ liệu hộ tịch điện tử, đăng ký hộ tịch trực tuyến;; Nghị định số 104/2022/NĐ-CP ngày 21/12/2022 của Chính phủ sửa đổi, bổ sung một số điều của các nghị định liên quan đến việc … |
| `marital-status-certificate` | Thủ tục cấp Giấy xác nhận tình trạng hôn nhân | 1.004873.000.00.00.H38 | https://dichvucong.laocai.gov.vn/trang-chu/tra-cuu/chi-tiet-thu-tuc?ma-thu-tuc=47920 | 2026-10-26 | Luật Hôn nhân và gia đình năm 2014;; Luật Hộ tịch năm 2014;; Nghị định số 123/2015/NĐ-CP ngày 15/11/2015 của Chính phủ quy định chi tiết một số điều và biện pháp thi hành Luật Hộ tịch;; Nghị định số 87/2020/NĐ-CP ngày 28/7/2020 của Chính phủ quy định về Cơ sở dữ liệu hộ tịch điện tử, đăng ký hộ tịch trực tuyến;; Nghị định số 104/2022/NĐ-CP ngày 21/12/2022 của Chính phủ sửa đổi, bổ sung một số điều … |
| `certified-copy` | Chứng thực bản sao từ bản chính giấy tờ, văn bản do cơ quan, tổ chức có thẩm quyền của Việt Nam; cơ quan, tổ chức có thẩm quyền của nước ngoài; cơ quan, tổ chức có thẩm quyền của Việt Nam liên kết với cơ quan, tổ chức có thẩm quyền của nước ngoài cấp hoặc chứng nhận | 2.000815.000.00.00.H38 | https://dichvucong.laocai.gov.vn/trang-chu/tra-cuu/chi-tiet-thu-tuc?ma-thu-tuc=47936 | 2026-10-26 | + Nghị định số 280/2025/NĐ-CP sửa đổi, bổ sung một số điều của Nghị định số 23/2015/NĐ-CP về cấp bản sao từ sổ gốc, chứng thực bản sao từ bản chính, chứng thực chữ ký và chứng thực hợp đồng, giao dịch, được sửa đổi, bổ sung bởi Nghị định số 07/2025/NĐ-CP;; + Nghị định số 23/2015/NĐ-CP về cấp bản sao từ bản chính, chứng thực chữ ký và chứng thực hợp đồng, giao dịch;; + Thông tư số 01/2020/TT-BTP qu … |
| `household-business` | Đăng ký thành lập hộ kinh doanh | 1.001612.000.00.00.H38 | https://dichvucong.laocai.gov.vn/trang-chu/tra-cuu/chi-tiet-thu-tuc?ma-thu-tuc=48106 | 2026-10-26 | Thông tư số 85/2019/TT-BTC ngày 29 tháng 11 năm 2019 của Bộ trưởng Bộ Tài chính hướng dẫn về phí và lệ phí thuộc thẩm quyền quyết định của HĐND tỉnh, thành phố trực thuộc Trung ương (được sửa đổi bổ sung tại Thông tư số 106/2021/TT-BTC ngày 26 tháng 11 năm 2021 và Thông tư số 75/2022/TT-BTC ngày 22 tháng 12 năm 2022 của Bộ trưởng Bộ Tài chính) Số: 85/2019/TT-BTC; Luật 59/2020/QH14 Số: 59/2020/QH14 … |
| `work-permit` | Cấp giấy phép lao động đối với người lao động nước ngoài làm việc tại Việt Nam | 1.014199.H38 | https://dichvucong.laocai.gov.vn/trang-chu/tra-cuu/chi-tiet-thu-tuc?ma-thu-tuc=118157 | 2026-10-26 | Bộ Luật lao động Số: 45/2019/QH14; Nghị quyết Số: 51/2023/NQ-HĐND; Nghị quyết Số: 39/2024/NQ-HĐND; QUY ĐỊNH VỀ NGƯỜI LAO ĐỘNG NƯỚC NGOÀI LÀM VIỆC TẠI VIỆT NAM Số: 219/2025/NĐ-CP |

Avertissements notés dans `data/procedures/catalog.json` (en anglais, tels quels) :
- `passport` : Source still cites Luật 49/2019/QH14; Luật 118/2025/QH15 amended it from 01/07/2026. Fee note on source refers to an expired rate.
- `foreigner-temp-residence-card` : Source cites Luật 47/2014/QH13 and 23/2023/QH15; check whether Luật 118/2025/QH15 (from 01/07/2026) changed it.
- `foreigner-stay-extension` : Same legal-basis caveat as foreigner-temp-residence-card.

### 6.3 Formulaires officiels

| Formulaire | Fichier officiel téléchargé | Texte juridique imprimé sur le formulaire | Statut |
|---|---|---|---|
| **CT01** : Tờ khai thay đổi thông tin cư trú | <https://dichvucong.bocongan.gov.vn/public_dir/tttl/01/giayto/2023_10/1698204115_CT01.doc> | Thông tư 56/2021/TT-BCA | vérifié à la main |
| **NA5** : Tờ khai đề nghị cấp thị thực, gia hạn tạm trú | <https://dichvucong.bocongan.gov.vn/public_dir/tttl/01/giayto/2022_06/1655667280_Mau-NA5--Don-xin-cap-visa-thi-thuc-Viet-Nam-2.doc> | Thông tư 04/2015/TT-BCA, 05/01/2015 | vérifié à la main |
| **TK05** : Đơn trình báo mất hộ chiếu phổ thông | <https://dichvucong.bocongan.gov.vn/public_dir/tttl/01/2024/08/MauTK05tt31e02d0_1723631335.doc> | Thông tư 31/2023/TT-BCA, 20/07/2023 | brouillon (agent) |
| **CC01** : Tờ khai căn cước công dân | <https://dichvucong.bocongan.gov.vn/public_dir/tttl/10/giayto/2020_11/1604372463_Mau_CC01.doc> | Thông tư 41/2019/TT-BCA, 01/10/2019 (voir 4.2) | brouillon (agent) |

Chaque fichier est copié dans `data/forms/<id>/` avec son `form.json`, dont le champ `source` donne l'URL et la date de téléchargement.

### 6.4 Autres sources

- Spécification produit : [`ho so ai.pdf`](../ho%20so%20ai.pdf) (racine du dépôt).
- Police des valeurs écrites : DejaVu Sans, licence libre (`data/fonts/README.txt`).
- Modèles locaux : `qwen2.5:7b` (et la variante `qwen2.5:7b-16k` avec un contexte de 16 384 tokens), `qwen2.5vl:7b` pour la vision, via [Ollama](https://ollama.com).

## 7. Ce qui reste à faire

- **Vérification finale avec OpenAI pour la démo.** Elle n'a pas été lancée : elle demande une clé payante, et `AGENTS.md` exige qu'un humain la demande explicitement. Il suffit de modifier le `.env` (voir le README, « Using OpenAI instead of Ollama »).
- **Sources à revérifier** (notées dans `catalog.json`) :
  - la page « passeport » cite encore la Luật 49/2019/QH14, modifiée par la Luật 118/2025/QH15 depuis le 01/07/2026 ;
  - les pages « carte de séjour » et « prolongation de séjour » des étrangers appellent la même vérification ;
  - le formulaire CC01 imprime un texte de 2019 (voir 4.2).
- **Formulaires appris** : TK05 et CC01 restent des brouillons. Une personne doit les relire avant de passer `"status": "reviewed"`.
- **Scans** : cases à chiffres et cases à cocher (voir 4.3).
- **Procédures non couvertes** (`catalog.json`, `not_yet_covered`) :
  - création d'une SARL : la seule page trouvée cite un décret remplacé ;
  - permis de conduire : déplacé vers un autre portail, pas encore vérifié.

## 8. Reproduire

```bash
cd apps/api && uv sync && uv run pytest          # 82 tests, aucune IA appelée
cd apps/web && pnpm install && pnpm test         # 8 tests
cd apps/api && uv run python -m hosoai.evals.run --part scanned   # éval scans, Ollama local
```

L'installation complète (Ollama, contexte 16k, lancement) est décrite dans le [README](../README.md).
