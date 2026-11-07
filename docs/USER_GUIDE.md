# MessMate user guide

MessMate collects feedback on the college mess food in three separate ways and shows it to the people who can act on it. This guide covers what each kind of user can do and what to expect.

| You are | Start here | Sign-in needed |
|---|---|---|
| A student | `/home`, today's menu | No |
| A food committee member | `/signin` | Yes, with the account the admin gave you |
| An admin | `/signin` or `/admin/login` | Yes, the admin password |
| A dean or other read-only viewer | `/signin`, or the dashboard link you were sent | Yes, or the link itself |

The three kinds of feedback are kept apart on purpose and are never averaged together. A tally of quick taps, a mean of 1 to 5 dish scores and a committee review measure different things from different people.

---

## For students

Nothing you submit is linked to you. MessMate stores no name, email, roll number or IP address with your feedback.

### See the menu

Open **`/home`**. It shows today's breakfast, lunch and dinner with serving times:

| Meal | Served |
|---|---|
| Breakfast | 7:30 to 9:30 am |
| Lunch | 12:00 to 2:30 pm |
| Dinner | 7:30 to 9:30 pm |

The row of day tabs lets you look at the rest of the week's menu. The meal buttons under the tabs show one meal at a time.

If a meal says **"Menu not published yet"**, the mess hasn't posted it. The meal is still being served, and you can still rate it after you eat.

The strip of moving text under the header has a **Pause** button on its right.

### Rate a meal in one tap

Each meal card has three buttons:

- **👍 Good**: you ate it and liked it.
- **👎 Bad**: you ate it and didn't.
- **⏭️ Skipped**: you didn't eat this meal.

To add a comment, open **Add a suggestion** and type it **before** you tap a button. The suggestion is sent with your tap.

After you tap, the card shows what you said, for example "You said 👍 Good for lunch today."

**The rules:**

- **One tap per meal per day.** Each phone or browser can rate breakfast, lunch and dinner once each, so up to three taps a day.
- **Only after the meal starts.** The buttons stay greyed out until the meal's serving time begins. A card says when it opens, for example "Dinner opens at 7:30 pm." Once open, a meal stays open for the rest of the day.
- **Only today.** Other days' menus can be viewed but not rated.
- **Changed your mind?** Press **Undo** on the card within **10 minutes** of tapping. Your rating is removed and the buttons come back. After 10 minutes the rating is final.

The percentage on a meal card is the share of students who ate that meal and liked it. Skips are counted separately and don't lower the score. A grey "--" means nobody who ate has rated it yet.

### Rate lunch dish by dish

For more detail on lunch, use **Rate dish by dish** at the bottom of the home page, or open **`/`** directly.

- **Overall score** (required): one of five faces, from 😡 to 😄.
- **Individual dishes** (optional): rice with curry, rice with rasam, chapati, chapati with gravy, poriyal, sweet or fruit, salad, curd, papad, and pickle or thogayal. Rate only what was served.
- **Comments** (optional): up to 150 characters.
- **Suggest a dish** (optional): something you'd like on the menu.

You can send **one dish-by-dish review every 4 hours** from the same phone or browser.

### Messages you might see

| Message | What it means |
|---|---|
| You've already rated lunch today | This device has rated that meal. Use Undo on the card within 10 minutes to change it. |
| Dinner isn't being served yet | The meal's serving time hasn't started. Try again once you've eaten. |
| Ratings open on the day itself | You're looking at another day. Switch back to today's tab. |
| This device has used today's three quick ratings | All three meals are rated from this device. Come back tomorrow, or rate lunch dish by dish. |
| That rating is more than 10 minutes old | Undo is no longer available for it. |
| You've already submitted a review in the last 4 hours | The dish-by-dish form allows one review every 4 hours per device. |
| Couldn't save that just now | A connection problem. Tap again. |

The limits are per phone or browser, not per person.

---

## For food committee members

Committee reviews are **not anonymous**. Your name and email are stored with every review you submit, so the administration can follow up.

### Sign in the first time

1. The admin adds you and gives you a one-time password.
2. Open **`/signin`** and enter your email and that password.
3. You'll be asked to choose your own password, at least **8 characters**. You can't review anything until you do.

After that, sign in at `/signin` with your own password. Sign out from the button at the top of any committee page.

If you forget your password, ask the admin to reset it. You'll get a new one-time password and choose a new one again.

### Review a meal

Open **`/committee`**. You review **each meal separately**, once per meal per day.

1. **Pick a meal.** The tabs at the top show Breakfast, Lunch and Dinner. A meal you still have to review is **yellow** and says **To review**. Once you've reviewed it, it turns **green** and says **✓ Reviewed**. The page opens on the meal most recently served that you haven't reviewed yet.
2. **Rate every dish** on that meal's menu from 1 to 5. Each dish on today's published menu gets its own card, so the list changes with the meal and the day. If the menu isn't published, there are no dishes to rate and you rate only the five areas.
3. **Rate the five areas** from 1 to 5:
   - **Taste**: flavour and seasoning of what was served.
   - **Quality**: freshness, temperature and cooking.
   - **Variety**: range and balance across the counters.
   - **Hygiene**: cleanliness of food, counters and utensils.
   - **Menu**: did the meal match the published menu?
4. **Add a written review** if it would help the kitchen act. This is optional, up to 500 characters.
5. Press **Submit**. The button only enables once every dish and all five areas are rated.

The thank-you page links to any meal you still have to review today.

If someone edits that meal's menu while you're rating, MessMate doesn't save your review. It shows the updated dishes and asks you to rate again, so scores are never filed under the wrong dish.

### Your dashboard

Open **`/committee/dashboard`**. It shows:

- **Today's committee score**, how many members have reviewed (and how many meal reviews that adds up to), the 7-day average and the lowest-scoring area today.
- **Your own record**: your meal reviews this month and your last review.
- **Today by area**, and the **7-day committee trend**.
- **Who has reviewed today.**
- **What students said today**, shown as context in its own card. It's never mixed into the committee score.
- **Recent committee reviews**, newest first, each labelled with its date and meal.

---

## For admins

Sign in at **`/signin`** with the admin email, or at **`/admin/login`**. You land on the overview.

### Overview

**`/admin`** puts today on one screen: the dish-form score, quick-tap results per meal, the committee score and participation, 7-day trends, the next week's menu status, who on the committee has reviewed, and the latest feedback.

The **Needs attention** list flags anything that needs a decision, for example:

- today's menu has a meal that isn't published,
- one of the next six days has an unpublished meal,
- students rate today's lunch, or a dish, below 2.5 out of 5,
- fewer than 40% of students liked a meal, once at least five have rated it,
- the committee scored an area below 2.5,
- from 3 pm, committee members who haven't reviewed any meal today,
- active members who haven't signed in to set their own password yet.

Each item links to the page that fixes it.

### Publish the menu

Students only see a menu once it's published. A meal left blank shows **"Menu not published yet"**. MessMate never shows students a made-up menu.

There are three ways to publish, and all three write to the same place:

**1. The weekly editor at `/admin/menu`.** One card per day, Monday to Sunday.

- Use **◀ Prev**, **This week** and **Next ▶** to move between weeks.
- Type dishes separated by commas, for example `Idli, Sambar, Coconut Chutney`. One dish per line also works.
- Empty fields show the standard weekly menu as a grey hint. Nothing is published until you save.
- **Fill blanks from template** copies the standard menu into empty fields. **Copy last week** copies last week's published menu into empty fields. Neither overwrites what you've typed.
- **Save** on a day card publishes that day. **Save all 7 days** publishes the whole week.

**2. Import a CSV**, from the **Import from CSV** card on the same page.

1. Press **Download blank template** for a CSV of the week you're viewing.
2. Fill it in a spreadsheet. The columns are `Date, Breakfast, Lunch, Dinner`. Dates are `YYYY-MM-DD`. Keep each meal's dishes in one cell, separated by commas.
3. Save it as a **UTF-8 CSV** under 1 MB, then press **Upload CSV**.

Importing a date that already has a menu updates it rather than adding a second copy. A blank cell publishes nothing for that meal. Rows with a bad date are skipped and listed by line number.

**3. The spreadsheet.** Staff can also type straight into the `menu` tab of the Google Sheet: one row per date, with `Date` in the first column.

Menus saved in the editor or by CSV reach students immediately. Edits typed into the spreadsheet show up within 30 seconds.

### Manage committee members

Open **`/admin/members`**.

- **Add a member**: enter a name and email.
- **Add many** at the start of a rotation: paste one member per line as `Name, email`. Lines with a problem are listed separately and the rest are still added.
- **Copy the one-time passwords straight away.** Only a scrambled version is stored, so they can't be shown again. **Copy all** copies every new password at once. Send each member theirs privately.
- **Reset** a password if someone is locked out. They get a new one-time password.
- **Deactivate** members who leave the committee, and **Activate** them if they return.

There's no delete. Deactivating keeps a member's past reviews and the record of who served when. To rotate the committee, deactivate the outgoing members and bulk-add the incoming ones.

### Dashboards

| Dashboard | Address | Shows |
|---|---|---|
| Student feedback | `/dashboard` | The dish-form score today and over 7 days, response count, best and lowest dish, each dish's score, the 7-day trend, quick-tap results per meal, and student suggestions from both the form and the quick taps |
| Committee | `/dashboard/committee` | The committee score, members reviewed, active members, participation, 7-day average, lowest area, today by area, the 7-day trend, who reviewed today, and the written reviews |

Scores out of 5 are coloured **red** below 2.5, **amber** up to 3.5 and **green** above. Quick-tap percentages are **red** below 40%, **amber** from 40 to 69% and **green** from 70%. A grey "--" means there's no data yet, not a zero.

---

## For deans and read-only viewers

Sign in at **`/signin`** with the viewer account. You can open both dashboards, **`/dashboard`** and **`/dashboard/committee`**, but you can't change the menu or the committee.

You may instead have been sent a dashboard link containing `?token=`. It opens the same two dashboards without signing in. **Don't forward it**: anyone with the link can read the dashboards.

---

## Demo and pilot mode

For a demonstration, the person running MessMate can switch on **pilot mode**. The `/signin` page then lists one ready-made account per role. Pick a card, press **Sign in**, and you see MessMate as that role. The demo data comes from `python seed_demo.py --yes`.

Pilot mode shows passwords on the page. It must be **off** for real use.

Setup, hosting and configuration are covered in the [README](../README.md).
