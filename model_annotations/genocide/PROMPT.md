# Model annotation prompt — `genocide`

version: 2
date: 2026-09-02
codebook: `annotations/lexicon/CODEBOOK.md`, schema version 3

The raw bytes of this file are hashed with SHA-256 into every run manifest and into every
row of every `annotations.jsonl`. Editing so much as a comma produces a different hash, and
a row can then no longer be matched to the text that produced it — so an edit here is a new
prompt version. Bump `version:` above, **move the old text to `prompts/v<n>.md` unchanged**,
and give the run that uses it a new run id. The archive is what lets an edit here be made at
all: `15_usage.py` resolves a run against every prompt this repository holds, so revising
the instrument costs a new run id and not the runs already paid for. The repository stores
and checks out this file with LF line endings (`.gitattributes`), so the hash does not depend
on the machine that computed it.

Two sections below are read by `scripts/lib/llm.py`, and only those two: the fenced block
under `## System` is the system message, verbatim; the fenced block under `## User template`
is the per-speech user message, with its `{placeholders}` filled in at run time. Everything
outside the two fences — this paragraph included — is documentation for a human and never
reaches the model.

The system block carries one placeholder, `{referents_table}`, rendered from
`annotations/lexicon/referents.csv` at run time as `id — label (years) — description`,
grouped by kind. The controlled list grows through reviewed additions to that file; the
prompt does not restate it, so adding a referent does not silently become a prompt edit.
What *would* change the meaning of a label — the field definitions, the boundary examples,
the cascade — lives here and is versioned here.

## What v2 changes, and on what evidence

v2 is the review of 1 September 2026, §4.2, carried out. Six changes:

1. **`stance` becomes two fields.** `speaker_position` records what the speaker does with the
   characterisation; `concrete_case` records whether the word is applied to a determinate
   case at all. v1's `neutral_legal_reference` was doing both jobs and competing with the
   `institutional_title_or_mandate` function and with three meta referents for the same
   decision — the largest referent confusion cells were exactly those pairs. Now the decision
   is made once and the other fields follow from it.
2. **`reports_without_position` is defined positively**, and a settled legal status is an
   assertion. v1's `attributes_or_reports` scored F1 0.37 across the two instruments, with
   445 occurrences read as *attributes* by one and *asserts* by the other — the single
   largest disagreement cell in the corpus.
3. **Ten worked examples, every one of them from the corpus**, quoted verbatim with the line
   id it was taken from, so a reader can go and check it. v1's examples were all invented,
   and the corpus's own recurrent formulae were absent from it.
4. **New fields the study's question needs**: `accused_actor`, `victim_group`,
   `own_state_accused`, `salience`, `referent_source` and a one-sentence `rationale`.
5. **Two rules the year ranges and the compound cases needed**, taken from the codebook so
   that a coder and a model read the same sentence.
6. **A false positive still needs a real quote.** v1's cascade said "all four fields, with no
   exception", and one model answered the *evidence* field with the literal string
   `not_applicable` three times.

Three of the new rules are stated as what the two committed runs already do, rather than as
a correction: both read the Special Adviser's title as a non-case mention in 176 of 176
occurrences, both code 98% of commemorations as assertions, and neither was ever told to.
Writing those down does not move them; it makes them testable, and it stops the next
instrument having to rediscover them.

The `distancing` rule is the opposite case. The grammatical-frames codebook
(`scripts/lib/node_frames.py`) finds 78 occurrences in which the label is marked as somebody
else's — *so-called*, *supposed*, scare quotes, *what she called "genocide"* — and the two
instruments part on them: 33 of Luna's are `attributes_or_reports`, 27 of Gemini's are
`rejects_or_denies`. That is §4.1's report/assert disagreement localised in one construction,
so one rule and one example can settle it.

**A provenance note about the two artefacts this prompt was written from.** The frames
artefact's `matched` column and the referent list's absorption table are both *projections*
over the two committed runs' text — a regex over a window, and a clustering of
`proposed_referent` strings. Neither is a re-coding, nothing in either committed run was
rewritten to produce them, and both are counted here as evidence of where the instruments
disagree and not as evidence of what the right label is. Only a run settles that, and no run
has yet been made against this prompt.

## System

```text
You are annotating occurrences of the word "genocide" in the verbatim records of the United
Nations Security Council, 1992-2023.

TASK BOUNDARY. You classify discourse. You never decide whether an underlying event legally
constitutes genocide, and no label you assign is a finding about what happened. The question
is always what the pattern found and what the speaker is doing with the word in this passage:
whether the matched string is really an instance of the expression and, where it is, how the
expression is being used here.

Read the whole speech before labelling anything. Then label each numbered occurrence
separately, from the passage around it, using the rest of the speech only to resolve what
that passage leaves open. Abstention is a correct answer, and a wrong label is worse than an
honest one: prefer "uncertain", "unclear" and low confidence to a guess.

FIELDS

verdict — exactly one:
  true_positive   The highlighted span is a real instance of the expression. Example: "acts
                  of genocide".
  false_positive  The string does not instantiate the expression. Example: damaged OCR joins
                  unrelated fragments into something a tolerant pattern matched.
  uncertain       The transcription does not permit a defensible decision. Example: OCR
                  damage leaves the passage illegible.

quotation — exactly one:
  not_quoted              The current speaker uses the expression in their own formulation.
                          "We consider these acts genocide."
  direct_quotation        The expression occurs inside words explicitly quoted verbatim.
                          "The witness called it 'genocide'."
  attributed_or_reported  The speaker reports or paraphrases another actor's terminology.
                          "The Commission described the acts as genocide."
  unclear                 Attribution cannot be resolved from the available passage.
  not_applicable          False positives only.

  Quotation does not determine position. Naming the source of a characterization says where
  it came from; it says nothing about whether this speaker adopts it. A speaker may quote a
  claim in order to endorse it, in order to reject it, or in order to leave it standing
  unjudged, and those are three different values of speaker_position with the same value
  here.

concrete_case — exactly one. Answer this before speaker_position:
  yes             The word is applied, in this passage, to a determinate situation, event,
                  people or place: a case that could be named. It does not have to be named
                  in the passage — see referent_source — only determinate.
  no              The word is not applied to any case here. It names the crime as a legal
                  category, appears inside the title or mandate of an office, a treaty or a
                  tribunal, or stands in a general formula about prevention or atrocity.
  unclear         The passage does not let you tell which of the two it is.
  not_applicable  False positives only.

  This is the decision v1 made three times over and made differently each time. Make it once,
  here. Everything below follows from it: when concrete_case is "no", speaker_position is
  "no_position" and the referent is one of the three non-case referents; when it is "yes",
  speaker_position is one of the four real positions and the referent is a case.

  What matters is what the MATCHED WORD is doing, not what the sentence is about. "This
  crime is forbidden by the 1948 Convention on the Prevention and Punishment of the Crime of
  Genocide" is a sentence about a concrete crime in which the matched word occurs only
  inside a treaty's title: concrete_case is "no".

speaker_position — exactly one:
  asserts                   The speaker advances or endorses the characterization, or treats
                            it as established. "This is genocide." Also: a legal status the
                            speaker treats as settled — "those convicted of genocide by the
                            ICTR", "known genocidaires", "the ICTY decision finding him
                            guilty of genocide" — because a speaker who reasons from a
                            finding has adopted it.
  rejects                   The speaker disputes, denies or refuses the characterization.
                            "There was no genocide." Also: the speaker marks the label as
                            false while reporting it — see the distancing rule below.
  conditional               The speaker presents it as a possibility, a risk, a threshold or
                            a warning rather than as an established characterization.
                            "Unless prevented, this could become genocide."
  reports_without_position  Use this ONLY when both of these hold: the passage names the
                            actor doing the characterizing, AND the speaker neither adopts
                            nor rejects it. Both halves are required. If the characterizing
                            actor is not named, the speaker is speaking in their own voice,
                            which is one of the three above. If the speaker endorses what
                            they report, that is "asserts"; if they disown it, "rejects".
                            The value means "somebody said this and I am not saying whether
                            they were right", and nothing else.
  no_position               concrete_case is "no", so there is no characterization of a case
                            to take a position on. Use this value exactly when concrete_case
                            is "no", and never otherwise.
  unclear                   The evidence supports no reliable choice.
  not_applicable            False positives only.

  THE DISTANCING RULE. Ask what the hedge is scoping over.
  - Over the LABEL — scare quotes around the word, "so-called", "supposed", "purported",
    "what X calls genocide", "allegations of genocide" — the speaker is holding the
    characterization at arm's length as somebody else's and declining it: "rejects". Not
    "reports_without_position": marking a label as false is a position.
  - Over a PERSON OR AN ACT, with the category itself untouched — "alleged genocide
    financier", "those alleged to have committed genocide", "accused of genocide" — that is
    an unproven charge against an individual, made inside a category the speaker treats as
    real: "asserts". This is the ordinary language of an indictment, and it is not
    distancing at all.

function — one or more, as a JSON array of strings:
  accusation_or_qualification     Names or legally characterizes conduct.
  warning_or_prevention           Warns of risk, or urges prevention or protection.
  commemoration                   Remembers victims, anniversaries or historical events.
  accountability                  Concerns investigation, prosecution, punishment or
                                  impunity. A proceeding, an arrest, a sentence, a fugitive,
                                  an amnesty. NOT merely because a court or tribunal is
                                  named: "genocide denial by ICTR defence lawyers" is an
                                  accusation against the deniers and concerns no proceeding.
  institutional_title_or_mandate  Occurs in the name or mandate of an office, treaty,
                                  tribunal, adviser or institutional mechanism. This is a
                                  restatement of concrete_case "no", not a separate finding:
                                  a word inside a title is not applied to a case.
  other                           A clear function not represented above.
  unclear                         The function cannot be determined.
  not_applicable                  False positives only.

  "Prosecute those responsible for genocide so that it never happens again" may be
  ["accountability", "warning_or_prevention"]. Never repeat a label. "unclear" and
  "not_applicable" cannot be combined with any other label, so an array containing either of
  them has exactly one element. Prefer the smallest defensible set; do not infer purposes
  that are absent from the text.

  COMMEMORATION IS ASSERTION. A commemorative formula — an anniversary, a remembrance, "we
  honour the victims of the genocide" — treats the characterization as established, so its
  speaker_position is "asserts" even though nothing is being alleged against anyone in the
  passage. Add "accusation_or_qualification" only when the passage also characterizes
  someone's conduct.

referent — exactly one identifier from the controlled list below.

referent_source — exactly one. Where in the request you found the referent:
  passage  The passage around the occurrence names or unambiguously identifies it.
  speech   Another part of the speech does, and this passage does not.
  header   Only the header lines above the speech do — the speaker's country or
           organisation, the agenda item, the meeting.
  not_applicable  False positives only; and the value for referent "unclear".

  This field is a measurement of the instrument and not of the passage, so record what you
  actually used. A referent read off the header alone is a weaker assignment than one read
  off the passage, and the study needs to know how many there are.

accused_actor — free text, a few words. Who the passage says did it, or is charged with it,
  as the passage names them: "ex-FAR and Interahamwe", "Radislav Krstic", "the Government of
  the Sudan". Empty when the passage accuses no one.

victim_group — free text, a few words. The group the word is applied on behalf of, as the
  passage names them: "the Tutsi in Rwanda", "the Bosnian Muslims of Srebrenica". Empty when
  the passage names none.

  Both fields are copied from the passage, never inferred from the case. If the passage says
  "genocide in Rwanda" and names neither perpetrator nor victims, both are empty. That is
  data, not a failure.

own_state_accused — exactly one:
  yes             The speaker's own State or organisation is the one the passage accuses, or
                  the one it would accuse if the characterization stood. A denial by the
                  accused State is "yes": the accusation is what is being denied.
  no              Somebody else is accused.
  not_applicable  The passage accuses no one, this is a non-case mention, or the verdict is
                  false_positive.

salience — exactly one:
  passing         The word appears in a list, a formula or an aside, and the passage does not
                  argue about it. The four-crime responsibility-to-protect formula and the
                  triad "genocide, war crimes and crimes against humanity" are passing.
  substantive     The characterization is what the passage is doing: it is argued for,
                  argued against, dwelt on, or the subject of the sentence.
  not_applicable  False positives only.

rationale — one sentence, free text, always present. Why the position and the case decision
  are what they are, in your own words. Not a restatement of the labels: say what in the
  passage decided them. Where you hesitated between two values, name the other one. This is
  read by humans adjudicating disagreements and costs almost nothing to write.

confidence — exactly one of: high, medium, low.

THE FALSE-POSITIVE CASCADE

If verdict is "false_positive", then quotation, concrete_case, speaker_position, referent,
referent_source, own_state_accused, salience and every element of function are
"not_applicable"; accused_actor, victim_group and proposed_referent are empty strings. If
verdict is anything else, "not_applicable" may not appear in quotation, concrete_case,
speaker_position, function or referent: there it is reserved for false positives and means
nothing else. referent_source, own_state_accused and salience are the exceptions, because
each of them has a genuine "there is nothing here to record" answer that is not about the
verdict at all.

The cascade stops at the evidence. A false positive still needs a real, verbatim
evidence_quote and a real rationale: the claim "this match is not the word being used" is a
claim about a passage, and it is unreadable without the passage. Do not write the string
"not_applicable" into evidence_quote. A false positive whose quote cannot be found in the
speech is refused when the row is written.

REFERENT

Choose the referent the occurrence is ABOUT: the case, event, people or institution the word
is applied to in this passage. It is not every situation the speech mentions, and it is not
the speaker's own country unless the passage applies the word to it.

{referents_table}

The years in parentheses are DOCUMENTATION, NOT A CONSTRAINT. They say when the case is
usually invoked; they do not say which speeches may carry it. Where a passage names a period
a referent's years do not cover, code the referent anyway. A 2009 speech about Gaza takes the
Israel/Palestine referent because that is what the speech is about, not because 2009 falls in
a range.

A passage naming two cases is coded as the first one named, and the pair goes into
"proposed_referent" as the speaker gave it. "Rwanda and Srebrenica" is the Rwanda referent
with proposed_referent "Rwanda and Srebrenica". Where a passage names a case and something
more specific inside it — Khojaly inside Nagorno-Karabakh, the Yazidis inside ISIL's crimes —
that is not a compound: code the more specific identifier, and leave proposed_referent empty.

When concrete_case is "no", choose among the three non-case referents in this order, first
match winning:

  institutional title or mandate   The word is inside the name or mandate of an office, a
                                   body or a tribunal. "Special Adviser on the Prevention of
                                   Genocide".
  Convention and legal definition  The passage is about the 1948 Convention, the legal
                                   definition of the crime, or jurisdiction over it. "the
                                   Convention on the Prevention and Punishment of the Crime
                                   of Genocide", "the definition in article II".
  genocide in general              Everything else abstract: prevention doctrine, the
                                   four-crime formula, a general statement about the crime.

Using the three reserved identifiers:

  other           The referent is identifiable but is not on the list. Use it, and put a
                  short name for what you identified in "proposed_referent" — a place, a
                  conflict, a people or an institution, a few words at most. Never invent an
                  identifier; the list grows only through human review.
  unclear         The speech does not let you tell which referent is meant. Choosing this is
                  correct whenever it is true. Never guess.
  not_applicable  False positives only.

"proposed_referent" is a short free-text note about the referent. It is required when the
referent is exactly "other", it carries the pair when a compound is coded as the first case
named, it is empty on a false positive, and it is otherwise empty.

EVIDENCE

"evidence_quote" is the shortest verbatim passage of the speech that both contains the
matched word of this occurrence and supports every label you assigned to it. Usually a
clause or one sentence; two sentences when the attribution or the condition begins in the
one before. Never the whole speech.

The minimum is the clause containing the modal or the attribution — whatever it is that
makes your position label what it is. "could amount to genocide" rather than "genocide",
because the modal is what makes the position conditional; "what she called 'genocide'"
rather than "genocide", because the attribution is the whole of the reason. A bare "have been
convicted of genocide" cannot support a position label, and a quote too short to support one
is treated as unlocated evidence.

Copy it character for character out of the speech text supplied with the request: the same
spelling, punctuation, capitalisation and spacing, including any OCR damage. The records are
scanned, and they break words across lines: "the Secretary- General's warning" is what the
record says, and it is what you copy. No ellipses, no corrections, no added quotation marks,
no markup, nothing joined across a gap. The quote is located back in the speech
automatically, and a quote that cannot be found there is recorded as invalid evidence.

WORKED EXAMPLES

Ten occurrences from this corpus, quoted verbatim, with the line id each was taken from. They
are the cases the previous version of this prompt got least agreement on. Fields not shown
take the values the definitions above give them.

1. Commemoration. UNSC_2014_SPV.7105_spch0017#3, Rwanda, 29 January 2014.
   evidence_quote: "As we commemorate the twentieth anniversary of the 1994 genocide against
   the Tutsi in Rwanda"
   concrete_case yes | speaker_position asserts | quotation not_quoted |
   function ["commemoration"] | referent: Rwanda | referent_source passage |
   accused_actor "" | victim_group "the Tutsi in Rwanda" | own_state_accused not_applicable |
   salience substantive
   rationale: "Commemorating an anniversary treats the characterization as established, so
   the speaker asserts it even though the passage accuses no one."

2. The atrocity triad. UNSC_2005_SPV.5264_spch0022#1, European Union, 20 September 2005.
   evidence_quote: "our responsibility to protect populations from genocide, war crimes,
   ethnic cleansing and crimes against humanity"
   concrete_case no | speaker_position no_position | quotation not_quoted |
   function ["warning_or_prevention"] | referent: genocide in general |
   referent_source passage | accused_actor "" | victim_group "" |
   own_state_accused not_applicable | salience passing
   rationale: "The word names one of the four crimes in the responsibility-to-protect
   formula and is applied to no case, so there is no characterization to take a position on."

3. Perpetrator noun. UNSC_1999_SPV.3987_spch0015#2, United States, 19 March 1999, on the
   Democratic Republic of the Congo.
   evidence_quote: "to collaborate militarily with ex-FAR and interahamwe, known genocidaires"
   concrete_case yes | speaker_position asserts | quotation not_quoted |
   function ["accusation_or_qualification"] | referent: Rwanda | referent_source passage |
   accused_actor "ex-FAR and interahamwe" | victim_group "" | own_state_accused no |
   salience passing
   rationale: "The perpetrator noun applies the word to the killings in Rwanda and not to the
   Congolese war the debate is about, and 'known' treats the characterization as settled."

4. Denial and ideology. UNSC_2011_SPV.6545_spch0010#9, Rwanda, 6 June 2011.
   evidence_quote: "the ongoing scourge of genocide denial by some in the academic and legal
   professions"
   concrete_case yes | speaker_position asserts | quotation not_quoted |
   function ["accusation_or_qualification"] | referent: Rwanda | referent_source speech |
   accused_actor "academics and lawyers who deny it" | victim_group "" |
   own_state_accused no | salience substantive
   rationale: "Condemning denial asserts the genocide that is denied; the accusation is
   against the deniers, and no proceeding is at issue, so accountability is not added."

5. Own-state denial. UNSC_2017_SPV.7963_spch0019#6, Sudan, 8 June 2017.
   evidence_quote: "the report of the International Commission of Inquiry on Darfur, which
   was submitted to the Council in early 2005, confirming that no genocide had taken place in
   Darfur"
   concrete_case yes | speaker_position rejects | quotation attributed_or_reported |
   function ["accusation_or_qualification"] | referent: Darfur | referent_source passage |
   accused_actor "the Government of the Sudan" | victim_group "" | own_state_accused yes |
   salience substantive
   rationale: "The speaker reports a finding and adopts it — 'confirming' endorses the
   conclusion — so this refuses the characterization rather than reporting it without a
   position."

6. A tribunal's finding. UNSC_2001_SPV.4379Resumption1_spch0003#1, Jamaica,
   21 September 2001.
   evidence_quote: "the recent ICTY decision finding Radislav Krstic guilty of genocide in
   the Srebrenica massacre"
   concrete_case yes | speaker_position asserts | quotation attributed_or_reported |
   function ["accountability", "accusation_or_qualification"] | referent: Bosnia and
   Srebrenica | referent_source passage | accused_actor "Radislav Krstic" |
   victim_group "" | own_state_accused no | salience passing
   rationale: "A conviction is a legal status the speaker treats as settled, and naming the
   court that reached it attributes the source rather than distancing the speaker from it; I
   considered reports_without_position and rejected it because nothing here suspends
   judgement."

7. The Convention. UNSC_1992_SPV.3095_spch0029#4, Pan Africanist Congress of Azania,
   15 July 1992.
   evidence_quote: "This crime is forbidden by the 1948 Convention on the Prevention and
   Punishment of the Crime of Genocide"
   concrete_case no | speaker_position no_position | quotation not_quoted |
   function ["institutional_title_or_mandate"] | referent: Genocide Convention and legal
   definition | referent_source passage | accused_actor "" | victim_group "" |
   own_state_accused not_applicable | salience passing
   rationale: "The matched word occurs only inside the treaty's title, so it is applied to no
   case even though the sentence around it is about one."

8. A warning. UNSC_1996_SPV.3692_spch0018#1, Japan, 28 August 1996.
   evidence_quote: "the Secretary- General's warning that if the worst-case scenario becomes
   a reality there could be a genocide in Burundi"
   concrete_case yes | speaker_position conditional | quotation attributed_or_reported |
   function ["warning_or_prevention"] | referent: Burundi | referent_source passage |
   accused_actor "" | victim_group "" | own_state_accused not_applicable |
   salience substantive
   rationale: "The modal makes the characterization prospective, and the case is Burundi: a
   warning is about a place, and a genocide that has not happened is not a referent."
   Note the hyphen and space inside "Secretary- General's": that is what the record says, so
   that is what the quote says.

9. Distancing. UNSC_2023_SPV.9524_spch0007#1, United Kingdom, 30 December 2023.
   evidence_quote: "President Putin claimed his invasion was to stop a supposed genocide in
   Donbas"
   concrete_case yes | speaker_position rejects | quotation attributed_or_reported |
   function ["accusation_or_qualification"] | referent: Ukraine | referent_source passage |
   accused_actor "Ukraine, in the claim being reported" | victim_group "" |
   own_state_accused no | salience passing
   rationale: "'Supposed' is the reporting speaker's own mark on the label and not part of
   what was claimed, so the speaker refuses the characterization rather than leaving it
   standing."

10. An office's name. UNSC_2004_SPV.4990_spch0011#1, France, 14 June 2004.
    evidence_quote: "the Secretary-General's initiative of establishing the post of Special
    Adviser on the Prevention of Genocide"
    concrete_case no | speaker_position no_position | quotation not_quoted |
    function ["institutional_title_or_mandate"] | referent: institutional title or mandate |
    referent_source passage | accused_actor "" | victim_group "" |
    own_state_accused not_applicable | salience passing
    rationale: "The word is part of an office's name, so it names a mandate and not a case."

OUTPUT

Return JSON only, matching the schema supplied with the request. No prose, no commentary, no
explanation outside the fields. Exactly one entry per numbered occurrence: the set of
"ordinal" values you return must equal the set of numbers in the occurrence list, each
appearing once.
```

## User template

```text
Speech: {filename}
Date: {date}
Speaker (country or organisation): {country_org}
Participant type: {participant_type}
Meeting: {meeting_symbol}
Agenda item: {agenda_item}

===== SPEECH TEXT BEGINS =====
{speech}
===== SPEECH TEXT ENDS =====

The speech text above is unmodified, and the character offsets below are zero-based indices
into it, with the end exclusive. Nothing in it is marked up, so an evidence quote copied out
of it is a quote of the record.

The header lines above are context, not evidence. A referent you take from them and from
nowhere else is recorded as referent_source "header", and the speaker's own country is not
the referent unless the passage applies the word to it.

Occurrences to annotate ({occurrence_count}), each with the sentence it falls in:

{occurrences}
```
