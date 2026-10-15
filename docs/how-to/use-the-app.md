# How to use the app

## Fill from a live game (website only)

1. Click **Fill from a live game**. The app loads this week's games from ESPN.
2. Tap the game in the list. Games in progress are at the top, marked LIVE.
   To pick a different game, click **Fill from a live game** again.
3. In a live game, the app selects the team with the ball. Before kickoff, it
   selects the away team. To change it, tap the other team under **Who has the
   ball?**.
4. The app fills in the teams, betting line and roof, and in a live game the
   score, clock, down, distance, ball spot and timeouts.
5. Check every field. The feed is unofficial and can be late or wrong. Then
   click **Get the call**.

## Set the situation

1. Pick the **Away** and **Home** teams (optional). Under **Who has the ball?**,
   click the team that has the ball. Every two-team input shows the away team on
   the left and the home team on the right. When the ball changes hands, the
   scores, timeouts and field side stay with their teams. The app sets the
   stadium, the kicker of the team with the ball, and the betting line from ESPN.
   For London, Mexico City or the Super Bowl, click **Neutral site**.
2. Enter the score for each team.
3. Click the **Quarter**. For overtime, click **OT**. Three short rows appear:
   - **Regular season** or **Playoffs**. Playoff overtime cannot end tied.
   - When the score is tied: **First drive of OT** (nobody has had the ball yet)
     or **Next score wins** (both teams have had it).
   - Regular season only: **If it ends tied**: **Half a win** (normal), **A
     loss** (you must win) or **A win** (a tie is enough).
   A live game fills in overtime and the playoffs from the feed.
4. Enter the **Clock** (minutes and seconds left in the quarter). The app shows
   if the two-minute warning is still to come.
5. Click the side of the field (for example **HOU side**) and set the yard
   line (1–50).
6. Click the **Down**. The app starts on 4th down.
7. Set **Yards to go**. On 4th & 1, click how far it is: **Inches**, **Not
   sure** or **About a yard**.
8. Click the number of timeouts for each team.
9. Home field is set by the Away and Home teams.
10. In the first half, click who gets the second-half kickoff.
11. Click **Get the call**. The app shows the results screen. To change the
    situation, click **Edit situation**. Your inputs stay.

Use the **−** and **+** buttons to change a number by 1. Hold a button to
repeat. The seconds and the yard line also have **−5** and **+5** buttons. The
app calculates only when you click **Get the call**.

On 1st, 2nd or 3rd down the app compares **Run a play** with **Kick a FG now**.
Use this when the clock is about to run out.

## Set the factors

Each factor has a switch. A factor that is off uses a neutral value. The
factors stay closed, and each one shows its value under its name. Tap the name
to open it. **Get the call** stays at the bottom of the phone screen.

| Factor | When on, set | When off, the engine uses |
|---|---|---|
| Weather | Wind (mph), temperature (°F), rain or snow | No wind, 70 °F, dry |
| Stadium | Roof (outdoors or dome), altitude | An average stadium |
| Team strength | Which team was favored before kickoff, and by how many points (for example "Texans by 6.5") | Equal teams, with the usual home-field edge for the home team |
| Kicker | A kicker, league average, or replacement level | A league-average kicker |

When you pick two teams, the app looks up the pre-game line on ESPN (the
scoreboard, then the game summary, which keeps the line after kickoff). If no
line is found, the app says so, sets the teams even and switches Team strength
off.

A dome cancels weather. The kicker list shows kickers with at least 10
attempts in the last two seasons.

## Share a call

1. On the results screen, click **Share this call**.
2. On a phone, pick an app to send it. On a computer, the link is copied; paste
   it in a message.
3. The message is only the call (for example "GO FOR IT.") and a link. In
   iMessage and Android messages the link shows a large preview with the down,
   the distance and the call.
4. The link opens the app at the same situation and shows the call.

To rebuild the preview images, run `py build/og_images.py` (needs Edge and
Node). It writes `app/og/` and `app/s/`.

## Play the weekly game

1. Click **Play**. The game has five fourth downs from last week.
2. For each play, click what you think the engine says: **Go for it**,
   **Field goal** or **Punt**.
3. The app shows the engine's call and what the coach did. You get a green
   square when you match the engine. The coach gets a green square when his
   real call matched the engine.
4. After play 5, click **Send**. Everyone plays the same five plays, so friends
   can compare cards. New plays come every Tuesday.

The five plays are the two costliest confident mistakes of the week, the best
call to go for it, and two kicks that were correct but close. Every play is a
confident call (at least 18 of the 20 resampled models agree), so each play has
one answer. The code is `quiz()` in `engine/weekly.py`.

## Play the 4th Down Duel

The Duel is a game for your group chat. You call each fourth down before the
engine does.

1. Before you click **Get the call**, click **Your call**: **Go for it**,
   **Field goal** or **Punt**. It shows only on 4th down. Click it again to
   clear it.
2. Click **Get the call**. The Duel card shows a square for each call:
   green = you agree with the engine; yellow = a toss-up, and you picked the
   other close option (half credit); black = a miss.
3. Under **What did the coach do?**, click the coach's real call. The coach gets
   a row of squares too.
4. Click **Send scorecard**. On a phone, pick Messages or another app. On a
   computer, the scorecard is copied; paste it in a message. The squares show in
   iMessage, Android messages and most chat apps.
5. For the next fourth down, click **Edit situation**, change the situation, and
   repeat. One card holds one game for one day. Click **New game** to start
   again.

The card stays on your device only.

## Put the app on your home screen

- iPhone (Safari): tap **Share**, then **Add to Home Screen**.
- Android (Chrome): tap the menu, then **Add to Home screen** or **Install app**.

## Read the output

The first bar is the **split**: how the 20 resampled models vote among the
options. It adds up to 100%. For example, "Go for it 95% · Field goal 5% · Punt
0%" means 19 of 20 models pick going for it.

The bars under **Win chance after each choice** show how often you win the
game if you choose each option. They are separate "what ifs" and do not add up
to 100%.

- **The call**: the option with the highest win probability. The line below it
  says why, in one sentence. "Toss-up" means
  the edge is under 1 point.
- **The split**: 90% or more for one option is a confident call; 70–85% is a
  lean; less is genuinely uncertain.
- **Detail boxes**: the odds and win probability behind each option.
- **Decision map**: the call at every spot and distance for the current score,
  clock and factors.

## See every game

1. Click **Games**. Pick a week at the top. The newest week opens first.
2. Each game shows both teams with a grade: **A+** means no confident mistakes;
   otherwise the team is ranked against every team-game since 2014 that had one.
3. Tap a game to see every fourth down: the coach's call, the engine's call, and
   what happened.
4. Under the games: the week's costliest calls, the best gutsy calls, and the
   season so far by team.

## See the grades

1. Click **Coaches**. The switch at the top picks the seasons: **Since 2021**
   (the default) grades only recent calls, so a long career is not judged by an
   older era's norms; **All since 2014** grades every call. Click a column name
   or use **Sort by** to sort. Click a coach to see his seasons and costliest
   calls.
2. Click **Kickers**. The table shows current kickers and the replacement level.

A **confident mistake** is a call where at least 18 of the 20 resampled models
agree the coach chose wrong. **Wins lost per season** adds up the win chance
those mistakes gave away, scaled to a 17-game season. For more, read the white
paper, section 5.
