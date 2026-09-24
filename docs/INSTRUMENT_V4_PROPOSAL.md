# Proposition — instrument v4 (prompt v4, codebook 4)

24 septembre 2026. **Statut : proposition à relire par les deux codeurs (FM, JG).** Rien
n'est activé. Le prompt v3 reste l'instrument des runs Qwen et Gemma, et la comparaison
entre les deux modèles n'est valable que s'ils répondent au même questionnaire. Un v4
exigera un nouvel identifiant de run et une nouvelle sonde. Suivi : [ROADMAP.md](ROADMAP.md),
items RV7, RV8, RV9 et RV17.

## 1. Ce qui motive la révision

- **Les identifiants de référents.** Sur les 77 refus du run `2026-09-08-qwen-131k`, 73 sont
  des libellés à la place d'identifiants (« genocide in general » pour
  `genocide_in_general`, « Bosnia and Srebrenica » pour `bosnia_srebrenica`). Les dix exemples
  commentés du prompt v3 écrivent eux-mêmes `referent: Rwanda` : le prompt enseigne l'erreur
  qu'il refuse ensuite. Un seul référent invalide fait rejeter tout le discours.
- **Les preuves non contiguës.** 11 lignes sur 3 608 (0,30 %) dans l'instantané du
  9 septembre citent un passage recomposé : phrase intermédiaire omise (SC01253-01-003#2),
  objection coupée (SC03454-02-003#1), ordre inversé (SC04127-01-006#1), orthographe
  corrigée (SC01745-01-023#1).
- **La règle de distanciation.** Le codebook 3 range « allegations of genocide » dans
  `rejects` et « accused of genocide » dans `asserts`. Or une allégation rapportée n'est pas
  une dénégation : SC00235-01-001#3 est codé `rejects` alors que le Pakistan nie avoir accusé
  le gouvernement indien, juste avant d'affirmer qu'il y a eu génocide (#4) ;
  SC03247-01-039#1 est codé `reports_without_position` pour « what it termed
  "genocide" » malgré la règle.
- **Le décodage.** Le run a décodé de façon déterministe (`temperature=0`). La fiche du modèle
  Qwen3.8-27B recommande `temperature=1.0, top_p=0.95, top_k=20` en mode raisonnement. La
  reconnaissance Gemma a tronqué 2 discours sur 12.

## 2. Changements proposés au prompt (v4)

1. **Déclarer `constraints: referent-enum, sentence-evidence`** dans l'en-tête. C'est déjà
   implémenté (`lib/llm.py`) et sans effet sur v3. Le schéma de sortie contient alors la
   liste exacte des identifiants actuels, les numéros d'occurrence de la requête et leur
   nombre : un décodeur guidé ne peut plus produire un référent invalide ni oublier une
   occurrence.
2. **Réécrire les exemples avec des identifiants** (`referent: rwanda`), et les citer par
   leurs identifiants v5.0 (`model_annotations/genocide/prompt_examples.csv`). Ces dix
   occurrences restent exclues de l'échantillon de référence.
3. **Preuve = phrases numérotées.** Le discours est présenté phrase par phrase, numérotées ;
   le modèle renvoie la première et la dernière phrase de la preuve. La preuve est contiguë
   par construction et toujours localisée ; le passage recomposé devient impossible.
4. **Paramètres de décodage** : les fixer après la mesure de `scripts/probe_sampling.py`
   (≈100 discours, moitié les plus longs) — taux de troncature, refus, et accord des
   étiquettes entre réglages. Moins de troncatures n'est un gain que si les étiquettes
   tiennent face à l'échantillon de référence.

## 3. Changement proposé au codebook (4) : l'engagement

Proposition : scinder `rejects` selon la typologie de l'**engagement** (Martin & White,
*The Language of Evaluation*, 2005), qui distingue précisément ce que la règle actuelle
confond :

| Valeur proposée | Engagement | Exemple |
|---|---|---|
| `asserts` | proclamer / monoglossique | « This is genocide. » |
| `denies` | désavouer : nier | « There was no genocide in Darfur. » |
| `distances` | attribuer : prendre ses distances | « the so-called genocide », « allegations of genocide », guillemets de mise à distance |
| `reports_without_position` | attribuer : reconnaître | « the Commission described the acts as genocide » |
| `conditional` | envisager | « this could become genocide » |
| `no_position` | — (pas de cas concret) | la Convention, le Conseiller spécial |

Conséquences : `distances` ne compte plus comme rejet dans le classement « Who rejects the
word » ; les runs v3 ne sont pas recodés automatiquement (une ligne `rejects` v3 est soit
`denies`, soit `distances`, et seul un codeur peut le dire).

À trancher par les codeurs : faut-il un champ séparé (`hedge_scope` : étiquette / personne /
acte) plutôt qu'une valeur de plus ? « alleged genocide financier » met en doute une
personne, pas la catégorie : `asserts` dans les deux options.

## 4. Protocole pilote

1. **Échantillon pilote hors référence** (30–40 occurrences) : les refus du run Qwen, les
   onze preuves non contiguës, et les cas frontières de la revue du 10 septembre —
   SC00228-01-002#1, SC00232-01-005#1–3, SC00211-01-007#1–2, SC00235-01-001#3–4,
   SC03247-01-039#1, SC03656-01-005#7, SC06880-01-031#10 — plus des paires construites pour
   chaque frontière (nier / prendre ses distances / rapporter).
2. **Codage indépendant** par les deux codeurs sous le codebook 4 proposé, avec la page
   hors ligne (`tools/coding_page.py`).
3. **Mesures séparées** : part d'identifiants valides et de preuves contiguës (modèle),
   accord humain champ par champ (κ et PABAK), matrice de confusion
   `denies`/`distances`/`reports_without_position`.
4. **Décision** : adopter, amender ou abandonner l'engagement ; figer le prompt v4 ; lancer
   Qwen et Gemma sous v4 avec de nouveaux identifiants de run.

## 5. Ce qui ne change pas

- Le prompt v3, ses runs et leurs identifiants restent lisibles et publiés tels quels.
- L'accord entre modèles mesure la stabilité, pas l'exactitude ; seul l'échantillon de
  référence mesure l'exactitude, et les parts corrigées (RV15) en dépendent.
