# Explanation: how the engine decides

This page explains the parts of the engine and why each part exists. For the
equations and the results, read the white paper.

## One question for every option

The engine asks one question for each option: after this choice, what is our
chance to win the game? It does not use points. Points ignore the score and
the clock. A field goal that ties the game with 4 seconds left is worth more
than 3 points.

## Parts

1. **Win-probability model.** It gives the chance to win from any snap. It
   learns from every play from 2014 to 2025. All other parts feed it.
2. **Conversion model.** It gives the chance to make the first down. It learns
   from 3rd and 4th downs together, because 4th-down attempts alone are few and
   biased.
3. **Field-goal model.** It gives the chance to make a kick from its distance,
   the weather, the stadium and the kicker.
4. **Punt model.** It gives where the opponent starts after a punt, from real
   punts from the same part of the field.
5. **Clock.** It moves the clock by the real time each kind of play takes. It
   stops the clock at the two-minute warning. It ends the half or the game.

## Why toggles

Each optional factor can be off, so you can see what it changes. Off does not
mean zero. Off means "an average situation for this factor".

## Why a bootstrap

The models learn from a finite number of games. A different sample of games
gives slightly different models. The engine fits 20 models on resampled games.
If most of them agree, the call is confident. If they disagree, the call is a
toss-up, and a coach who chose differently did not make a mistake.

## Why two engines

The app runs in a browser, so it uses JavaScript. The pipeline uses Python. The
two engines do the same calculation. A test in CI checks that they give the
same numbers.
