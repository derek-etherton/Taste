# How Taste works, in plain language

This walks through the maths behind the prototype without assuming any. Each section says what the app does, why, and what you'd see. Exact formulas are in the code's docstrings, mainly `taste/model/user_model.py` and `taste/model/traits.py`.

## 1. Every film and book is a list of ingredients

Every item comes with a score for each of several hundred descriptive tags: "dark", "funny", "dystopia", "horror", "slow-paced" and so on. Each score runs from 0 ("doesn't apply at all") to 1 ("applies very strongly"). Think of it as an ingredient list with amounts.

Films have 1,128 tags and books have 727. 512 tags appear in both; those are the **shared traits** (section 6).

### Relative to normal

Raw scores are misleading. Almost every film is a bit "dramatic", so a high "dramatic" score says little. We therefore subtract the score of a *typical* item: the average, weighted towards items people actually watch or read. After that, each number says how unusual this item is on that tag.

- *The Shining* scores well above average on "creepy".
- A romcom scores below average.
- Most items score about average on most tags.

## 2. Your taste is a row of dials

For each tag the app keeps a dial for you:
- **turned up** means you like more of it;
- **turned down** means you'd rather have less;
- **in the middle** means you don't care, or we don't know yet.

An item's match score is: for every tag, multiply how unusual the item is on that tag by your dial, then add it all up. A very creepy film scores well if your "creepy" dial is up and badly if it's down.

Because the score is a plain sum, it can always be taken apart. The percentile button on each row shows which tags pushed the item up and which pulled it down. Nothing is hidden.

**Percentile.** The score is turned into a percentile among the items you haven't rated. "94th pct" means it beats 94% of them.

**Quality.** A small, adjustable bonus for items that everyone rates well (the *Weight on general quality* slider). It keeps "what's good" separate from "what's you".

## 3. Learning the dials from your ratings

Each rating is a clue:
- 👍 means this item's mix of ingredients should come out positive (+1);
- 👎 means it should come out negative (−1);
- 😐 means it should come out around zero.

**Why meh is useful.** It tells the app that this item's standout ingredients don't matter much to you, which is real information.

The app sets the dials so your rated items come out close to your ratings, but it does so cautiously:

- **Ratings are treated as noisy.** You might like a film for reasons no tag captures, or rate on a whim. The app assumes rating noise is about as large as a typical item's taste signal.
- **One rating gets you about halfway.** Because of that assumption, rating an item moves the prediction for that item about halfway from where it was towards your rating, not all the way. A second similar rating moves it further, and so on.
- **Dials start in the middle.** With no ratings they all sit at zero ("no opinion"), and they only move as far as the evidence pushes them.

This is a standard technique called *Bayesian ridge regression*: a sensible starting guess, updated by evidence, with each piece of evidence trusted only so far.

### Credit is shared out

If you like *Alien*, the app can't tell whether it was the horror, the sci-fi or the claustrophobia, so it turns all of them up a little. As you rate more items, the dials sort themselves out: liking other horror but disliking other sci-fi separates them.

## 4. Which items to ask you about (the *Rate* list)

Because the app tracks how *sure* it is about your dials, it can also tell which items it's least sure about. Rating one of those teaches it the most.

The Rate list starts with the 600 best-known items (so you've probably seen or read them), ordered by how uncertain your predicted reaction is. It picks them one at a time, each time assuming you'd already rated the earlier picks. That keeps it from asking about ten near-identical items. After those, the rest of the catalogue follows, best-known first.

## 5. Your profile

The Profile tab lists the dials turned furthest up ("You respond to") and down ("You push back on"). Each comes with evidence: rated items that clearly have that ingredient.

- **for:** items you rated in the direction of the dial.
- **against:** items you rated the other way, or meh'd.

Items that merely *lack* an ingredient aren't listed, even though the maths uses them a little. "You liked a film because it wasn't a western" isn't a convincing explanation.

## 6. Two kinds of item, one person

The core idea is that taste belongs to the person, not the medium. Someone who loves bleak dystopian films may well love bleak dystopian novels.

### A shared vocabulary

512 tags mean the same thing for films and books ("dystopia" is "dystopia"). The other tags are specific to one medium, like "great soundtrack" for films or "unreliable narrator" for books.

### Matching the volume

The book tag scores were produced by a different process and are "quieter": about half as spread out as the film scores. Before comparing, each shared tag is rescaled in each domain so that "unusually dystopian *for a book*" lines up with "unusually dystopian *for a film*".

That's a volume adjustment per medium, not a flattening. Broad themes like "dark" still matter more than niche ones like "autism". (An earlier version flattened everything to equal size, and niche tags carried by a single film took over the profile.)

**Does it work?** For about 1,000 films that share a title with a book (mostly adaptations), the film and its book come out far more alike than random pairs. A matched pair beats a random pair about 85% of the time.

## 7. Two layers of taste

The app models your taste in two layers:

- **Shared taste:** dials on the 512 shared traits, the same person across media.
- **Film-only taste and book-only taste:** extra dials for what's specific to each medium. You might love slow-burn pacing in novels but not in films.

An item's score is its shared-taste part plus its own-medium part.

The app assumes a typical item's taste is half shared, half medium-specific. That split is a single setting in the code (`SHARE` in `taste/model/traits.py`):
- **0:** films and books would be learnt completely separately.
- **Higher:** your films shape your book recommendations more, and your book ratings overrule your films less.

## 8. How your films inform your books

The app first works out your shared taste from your film ratings. This gives two things:

1. **A best guess,** e.g. you like dark, dystopian, intense. This is the book profile's *starting point*. With no books rated, book recommendations come entirely from it, and the popover shows how much of each book's score came from your films.
2. **How sure that guess is,** direction by direction. A taste you've shown consistently across many films is surer than one hinted at by a single film.

When you rate books, the book profile starts from the film-based guess. It only corrects what the books show to be wrong, and only as far as the guess was unsure. Your film ratings never change because of book ratings.

### A worked example from real data

The first book of a well-known dystopian trilogy, rated after 30 films:

| Your book ratings | Predicted score for book 1 | Share of the way to your rating | Same author, different series | *Pride and Prejudice* |
|---|---|---|---|---|
| none (films only) | +0.28 | n/a | +0.10 | −0.02 |
| 👍 book 1 | +0.67 | 53% | +0.23 | −0.03 |
| 👍 books 1–2 | +0.78 | 69% | +0.30 | −0.03 |
| 👍 books 1–3 | +0.87 | 82% | +0.33 | −0.05 |
| 👎 book 1 | −0.40 | 53% | −0.13 | −0.01 |
| 👎 books 1–3 | −0.67 | 75% | −0.27 | −0.02 |

The table shows three things:
- **One rating moves its own book about halfway.** Further similar ratings take it most of the way.
- **Similar books move too, by less.** The same author's other novel rises from +0.10 to +0.33.
- **Unrelated books barely move.** *Pride and Prejudice* stays near zero. Your book ratings only correct the kinds of book you've rated; elsewhere your films stay in charge.

### Why more films don't make it much surer

You'd expect 30 horror films to make the app very sure about horror books. They do so only a little. Disliking one horror book still moves it about halfway, almost as much as with no films at all. Two reasons:

- **Liked films pin down a blend, not individual tags.** Every horror film you like is high on horror *and* scary *and* creepy *and* dark at once. The app learns that you like that blend, but can't tell which ingredient does the work, so each tag on its own stays uncertain.
- **A book only partly matches that blend.** *The Shining* also has its own mix (classic, isolation, insanity), and only the part matching the blend gets surer. 30 horror films cut its uncertainty by about 20%.

The planned fix is to group ingredients that always move together into a few broader dimensions of taste. Then a handful of ratings can pin down far more.

## 9. Small things that make lists sensible

- **Book series** aren't treated specially: each volume is its own item, scored and rated on its own.
- **Explanations stay honest.** Once you've rated some books, a book's reasons are labelled "(from films)" where your film ratings, not your book ratings, account for most of that tag's pull.

## Known weak spots

- Ingredients are treated as independent (section 8). This is the main thing to fix next.
- Some tags track acclaim as much as taste ("oscar (best actor)", "inspirational"), so quality leaks into the dials.
- The source tag scores have occasional nonsense, such as a racing anime scoring high on "race", which can surface oddities.
