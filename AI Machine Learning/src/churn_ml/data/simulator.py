"""Agent-style simulator of a subscription telecom business.

Every customer carries a hidden *satisfaction* state that evolves week by week.
Outages, price increases, promo expiries, slow ticket resolution and (optionally)
a competitor launch push it down; good service pulls it back toward the
customer's baseline. Satisfaction drives everything observable:

* weekly product usage (sessions, minutes, data),
* support tickets (volume, category, free-text wording, CSAT),
* monthly invoices and late payments,
* and finally the weekly hazard of churning.

The hidden state is never written out, so models must recover it from the
observable behaviour, just like with real data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ..logging_utils import get_logger
from ..settings import SimulationConfig

log = get_logger(__name__)

REGIONS = np.array(["north", "south", "east", "west"])
PLANS = np.array(["basic", "standard", "premium"])
PLAN_PRICE = np.array([30.0, 55.0, 85.0])
INTERNET = np.array(["fiber", "dsl", "none"])
INTERNET_PRICE = np.array([25.0, 10.0, 0.0])
CONTRACTS = np.array(["month-to-month", "one-year", "two-year"])
CONTRACT_EFFECT = np.array([0.0, -0.9, -1.6])
PAYMENTS = np.array(["credit-card", "bank-transfer", "electronic-check", "mailed-check"])
CHANNELS = np.array(["online", "retail-store", "partner", "referral"])
TICKET_CATEGORIES = np.array(["billing", "technical", "cancellation", "account", "general"])

PROMO_WEEKS = 26
NO_CHURN = np.iinfo(np.int32).max

TOPIC_PHRASES = {
    "billing": [
        "my bill went up again",
        "question about the charges on my invoice",
        "why did my discount end",
        "i was charged twice this month",
        "need help understanding my bill",
        "the new price is too high",
    ],
    "technical": [
        "internet keeps dropping",
        "connection is very slow in the evenings",
        "outage in my area again",
        "router keeps restarting",
        "wifi signal is weak",
        "streaming keeps buffering",
    ],
    "cancellation": [
        "how do i cancel my contract",
        "what are the cancellation fees",
        "considering switching provider",
        "please close my account",
        "want to end my subscription",
    ],
    "account": ["update my payment details", "change my address", "reset my password", "add a user to my account"],
    "general": [
        "question about available plans",
        "how do i upgrade my package",
        "asking about the streaming bundle",
        "information about roaming",
    ],
}
TONE_PHRASES = {
    "negative": [
        "this is unacceptable",
        "very frustrated with the service",
        "not happy at all",
        "this keeps happening",
        "really disappointed",
    ],
    "neutral": ["please advise", "thanks", "let me know", "when you have time"],
    "positive": ["thanks for the quick help", "great service as always", "appreciate the support"],
}
COMPETITOR_PHRASE = "a competitor just launched a cheaper offer in my area"


@dataclass
class SimulatedData:
    customers: pd.DataFrame
    usage: pd.DataFrame
    billing: pd.DataFrame
    tickets: pd.DataFrame

    TABLES = ("customers", "usage", "billing", "tickets")

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for name in self.TABLES:
            getattr(self, name).to_parquet(directory / f"{name}.parquet", index=False)

    @classmethod
    def load(cls, directory: Path) -> SimulatedData:
        missing = [n for n in cls.TABLES if not (directory / f"{n}.parquet").exists()]
        if missing:
            raise FileNotFoundError(f"Raw tables {missing} not found in {directory}. Run `churn-ml simulate` first.")
        return cls(**{n: pd.read_parquet(directory / f"{n}.parquet") for n in cls.TABLES})

    def summary(self) -> dict[str, int | float]:
        churned = self.customers["churn_week"].notna()
        return {
            "customers": len(self.customers),
            "churned_customers": int(churned.sum()),
            "usage_rows": len(self.usage),
            "invoices": len(self.billing),
            "tickets": len(self.tickets),
        }


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


class CustomerSimulator:
    def __init__(self, config: SimulationConfig, seed: int = 42):
        self.cfg = config
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------ setup
    def _create_customers(self) -> dict[str, np.ndarray]:
        rng, cfg = self.rng, self.cfg
        initial_tenure = np.clip(rng.exponential(70, cfg.n_customers), 1, 320).astype(np.int32)
        arrivals = rng.poisson(cfg.new_customers_per_week, cfg.n_weeks)
        signup_week = np.concatenate([-initial_tenure, np.repeat(np.arange(cfg.n_weeks, dtype=np.int32), arrivals)])
        n = len(signup_week)
        long_tenure = signup_week < -52

        contract_p = np.where(long_tenure[:, None], [0.40, 0.30, 0.30], [0.65, 0.22, 0.13])
        contract = (rng.random(n)[:, None] > np.cumsum(contract_p, axis=1)).sum(axis=1)
        c = {
            "signup_week": signup_week,
            "age": rng.integers(18, 86, n).astype(float),
            "region": rng.integers(0, 4, n),
            "plan": rng.choice(3, n, p=[0.40, 0.42, 0.18]),
            "internet": rng.choice(3, n, p=[0.48, 0.38, 0.14]),
            "streaming": rng.random(n) < 0.42,
            "contract": contract,
            "payment": rng.choice(4, n, p=[0.32, 0.24, 0.30, 0.14]),
            "channel": rng.choice(4, n, p=[0.45, 0.25, 0.18, 0.12]),
            "paperless": rng.random(n) < 0.6,
            "dependents": rng.poisson(0.7, n),
        }
        # New customers often join on a promotional discount that later expires.
        c["promo"] = (signup_week >= -PROMO_WEEKS) & (rng.random(n) < 0.45)
        c["promo_pct"] = np.where(c["promo"], rng.uniform(0.10, 0.25, n), 0.0)
        c["base_charge"] = PLAN_PRICE[c["plan"]] + INTERNET_PRICE[c["internet"]] + 12.0 * c["streaming"]
        # About a third of customers get a single list-price increase.
        hit = rng.random(n) < 0.35
        c["price_week"] = np.where(hit, rng.integers(8, cfg.n_weeks, n), NO_CHURN)
        c["price_factor"] = rng.uniform(1.08, 1.18, n)

        # Hidden traits.
        c["base_sat"] = 0.8 * rng.normal(size=n) + 0.35 * (c["channel"] == 3) - 0.15 * (c["internet"] == 0)
        c["price_sens"] = rng.normal(size=n) + 0.5 * (c["payment"] == 2)
        c["engagement"] = rng.lognormal(np.log(9), 0.4, n) * (1 + 0.3 * c["streaming"])
        return c

    # ------------------------------------------------------------- main loop
    def run(self) -> SimulatedData:
        cfg, rng = self.cfg, self.rng
        c = self._create_customers()
        n = len(c["signup_week"])
        sat = c["base_sat"] + rng.normal(0, 0.3, n)
        churn_week = np.full(n, NO_CHURN, dtype=np.int32)
        service_feedback = np.zeros(n)  # carry-over effect of last week's ticket handling
        cancel_intent = np.zeros(n, dtype=np.int32)  # weeks left of an open cancellation enquiry
        considering = np.zeros(n, dtype=bool)  # 'thinking about leaving' phase that precedes most churn
        drift = cfg.drift
        drift_region = int(np.flatnonzero(REGIONS == drift.region)[0]) if drift.enabled else -1

        usage_parts, bill_parts, ticket_parts = [], [], []
        for w in range(cfg.n_weeks):
            idx = np.flatnonzero((c["signup_week"] <= w) & (churn_week > w))
            m = len(idx)
            s = sat[idx]
            tenure = w - c["signup_week"][idx]

            outage_regions = rng.random(4) < 0.04
            outage = outage_regions[c["region"][idx]] & (c["internet"][idx] != 2) & (rng.random(m) < 0.7)
            price_hit = c["price_week"][idx] == w
            promo_end = c["promo"][idx] & (c["signup_week"][idx] + PROMO_WEEKS == w)
            competitor = (drift.enabled and w >= drift.start_week) & (c["region"][idx] == drift_region)
            sens = 1 + 0.5 * np.clip(c["price_sens"][idx], -1, 2)

            s = (
                0.9 * s
                + 0.1 * c["base_sat"][idx]
                + rng.normal(0, 0.2, m)
                - 0.9 * outage
                - 0.55 * sens * price_hit
                - 0.45 * sens * promo_end
                + service_feedback[idx]
                - drift.satisfaction_shock * competitor
            )
            sat[idx] = s
            service_feedback[idx] = 0.0

            # Unhappy customers drift into a 'considering leaving' phase; some recover.
            enter = ~considering[idx] & (rng.random(m) < _sigmoid(-3.6 - 1.1 * s))
            recover = considering[idx] & (rng.random(m) < 0.12)
            considering[idx] = (considering[idx] | enter) & ~recover
            thinking = considering[idx]

            # Usage --------------------------------------------------------
            season = 1 + 0.08 * np.sin(2 * np.pi * w / 52)
            rate = (
                c["engagement"][idx]
                * np.exp(0.55 * s)
                * season
                * (1 - 0.5 * outage)
                * (1 - 0.45 * thinking)
                * (1 - drift.usage_drop * competitor)
            )
            sessions = rng.poisson(rate)
            minutes = sessions * rng.gamma(2.0, 9.0, m)
            data_gb = np.where(c["internet"][idx] == 2, 0.0, minutes * 0.015 * rng.lognormal(0, 0.3, m))
            usage_parts.append(
                pd.DataFrame(
                    {
                        "customer_id": idx.astype(np.int32),
                        "week": np.int16(w),
                        "sessions": sessions.astype(np.int16),
                        "minutes": minutes.astype(np.float32),
                        "data_gb": data_gb.astype(np.float32),
                    }
                )
            )

            # Tickets ------------------------------------------------------
            lam = 0.05 * np.exp(-0.8 * s) + 0.12 * thinking + 0.6 * outage + 0.5 * price_hit + 0.4 * promo_end
            n_tickets = np.minimum(rng.poisson(lam), 3)
            if n_tickets.any():
                t_pos = np.repeat(np.arange(m), n_tickets)
                ticket_parts.append(
                    self._tickets(
                        w,
                        idx[t_pos],
                        s[t_pos],
                        thinking[t_pos],
                        outage[t_pos],
                        price_hit[t_pos] | promo_end[t_pos],
                        np.broadcast_to(competitor, (m,))[t_pos],
                    )
                )
                last = ticket_parts[-1]
                slow = last["resolution_hours"].to_numpy() > 48
                service_feedback[last["customer_id"].to_numpy()] += np.where(slow, -0.35, 0.12)
                cancels = last["customer_id"].to_numpy()[last["category"].to_numpy() == "cancellation"]
                cancel_intent[cancels] = 4

            # Billing (every 4 weeks) -------------------------------------
            if w % 4 == 0:
                promo_active = c["promo"][idx] & (w < c["signup_week"][idx] + PROMO_WEEKS)
                discount = np.where(promo_active, c["promo_pct"][idx], 0.0)
                factor = np.where(w >= c["price_week"][idx], c["price_factor"][idx], 1.0)
                amount = c["base_charge"][idx] * factor * (1 - discount)
                late_p = _sigmoid(
                    -2.6 + 0.9 * np.isin(c["payment"][idx], [2, 3]) - 0.5 * s + 0.3 * (c["price_sens"][idx] > 1)
                )
                late = rng.random(m) < late_p
                bill_parts.append(
                    pd.DataFrame(
                        {
                            "customer_id": idx.astype(np.int32),
                            "week": np.int16(w),
                            "amount": amount.round(2).astype(np.float32),
                            "discount_pct": discount.round(3).astype(np.float32),
                            "paid_late": late,
                            "days_late": np.where(late, rng.geometric(0.15, m), 0).astype(np.int16),
                        }
                    )
                )

            # Churn --------------------------------------------------------
            logit = (
                -5.6
                - 0.5 * s
                + 2.6 * thinking
                + CONTRACT_EFFECT[c["contract"][idx]]
                + 0.45 * (c["payment"][idx] == 2)
                + 1.3 * (cancel_intent[idx] > 0)
                - 0.004 * np.minimum(tenure, 200)
                + 0.25 * (c["age"][idx] >= 65)
                - 0.12 * c["dependents"][idx]
            )
            leaving = rng.random(m) < _sigmoid(logit)
            churn_week[idx[leaving]] = w
            cancel_intent[idx] = np.maximum(cancel_intent[idx] - 1, 0)

        data = self._assemble(c, churn_week, usage_parts, bill_parts, ticket_parts)
        log.info("Simulated %s", data.summary())
        return data

    # ---------------------------------------------------------------- tickets
    def _tickets(
        self,
        week: int,
        cust: np.ndarray,
        s: np.ndarray,
        thinking: np.ndarray,
        outage: np.ndarray,
        price_event: np.ndarray,
        competitor: np.ndarray,
    ) -> pd.DataFrame:
        rng = self.rng
        k = len(cust)
        background = rng.choice(5, k, p=[0.25, 0.30, 0.03, 0.20, 0.22])
        category = np.where(outage, 1, np.where(price_event, 0, background))
        category = np.where((thinking | (s < -1.2)) & (rng.random(k) < 0.45), 2, category)

        hours = rng.lognormal(np.log(18), 0.8, k) * np.where(category == 1, 1.5, 1.0)
        csat = np.clip(np.round(3.4 + 0.7 * s - 0.015 * (hours - 24) + rng.normal(0, 0.7, k)), 1, 5)
        tone = np.where(s < -0.5, "negative", np.where(s > 0.7, "positive", "neutral"))

        texts = []
        for cat, tn, comp in zip(TICKET_CATEGORIES[category], tone, competitor):
            topic = TOPIC_PHRASES[cat][rng.integers(len(TOPIC_PHRASES[cat]))]
            words = TONE_PHRASES[tn][rng.integers(len(TONE_PHRASES[tn]))]
            extra = f" {COMPETITOR_PHRASE}" if comp and rng.random() < 0.35 else ""
            texts.append(f"{topic} {words}{extra}")

        return pd.DataFrame(
            {
                "customer_id": cust.astype(np.int32),
                "week": np.int16(week),
                "category": TICKET_CATEGORIES[category],
                "text": texts,
                "resolution_hours": hours.round(1).astype(np.float32),
                "csat": csat.astype(np.int8),
            }
        )

    # --------------------------------------------------------------- assemble
    def _assemble(self, c, churn_week, usage_parts, bill_parts, ticket_parts) -> SimulatedData:
        rng, start = self.rng, pd.Timestamp(self.cfg.start_date)
        n = len(churn_week)
        age = c["age"].copy()
        age[rng.random(n) < 0.02] = np.nan
        payment = PAYMENTS[c["payment"]].astype(object)
        payment[rng.random(n) < 0.01] = None

        churned = churn_week != NO_CHURN
        customers = pd.DataFrame(
            {
                "customer_id": np.arange(n, dtype=np.int32),
                "signup_week": c["signup_week"],
                "signup_date": start + pd.to_timedelta(c["signup_week"] * 7, unit="D"),
                "age": age,
                "region": REGIONS[c["region"]],
                "plan": PLANS[c["plan"]],
                "internet_service": INTERNET[c["internet"]],
                "has_streaming": c["streaming"],
                "contract_type": CONTRACTS[c["contract"]],
                "payment_method": payment,
                "paperless_billing": c["paperless"],
                "dependents": c["dependents"].astype(np.int16),
                "acquisition_channel": CHANNELS[c["channel"]],
                "churn_week": pd.array(np.where(churned, churn_week, 0), dtype="Int32"),
            }
        )
        customers.loc[~churned, "churn_week"] = pd.NA
        customers["churn_date"] = start + pd.to_timedelta(customers["churn_week"].astype("float") * 7, unit="D")

        usage = pd.concat(usage_parts, ignore_index=True)
        billing = pd.concat(bill_parts, ignore_index=True)
        billing["invoice_date"] = start + pd.to_timedelta(billing["week"].astype(int) * 7, unit="D")
        tickets = pd.concat(ticket_parts, ignore_index=True)
        tickets.insert(0, "ticket_id", np.arange(len(tickets), dtype=np.int32))
        offset = rng.uniform(0, 7, len(tickets))
        tickets["created_at"] = (
            start + pd.to_timedelta(tickets["week"].astype(int) * 7, unit="D") + pd.to_timedelta(offset, unit="D")
        ).dt.floor("min")
        return SimulatedData(customers, usage, billing, tickets)


def simulate(config: SimulationConfig, seed: int = 42) -> SimulatedData:
    return CustomerSimulator(config, seed).run()


def week_to_date(start_date, week: int) -> pd.Timestamp:
    return pd.Timestamp(start_date) + timedelta(weeks=week)
