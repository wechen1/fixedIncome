"""
This script contains classes for a Term interest rate swap and Overnight Interest Rate Swap.

"""
from enum import Enum
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import NamedTuple, Optional, Callable
from dataclasses import dataclass
import itertools

from fixedIncome.src.scheduling_tools.scheduler import Scheduler
from fixedIncome.src.scheduling_tools.day_count_calculator import DayCountCalculator
from fixedIncome.src.scheduling_tools.holidays import Holiday
from fixedIncome.src.assets.base_cashflow import Payment, Cashflow, CashflowKeys, CashflowCollection
from fixedIncome.src.curves.base_curve import Curve, DiscountCurve, KnotValuePair
from fixedIncome.src.curves.curve_enumerations import CurveIndex
from fixedIncome.src.scheduling_tools.schedule_enumerations import (BusinessDayAdjustment,
                                                                    SettlementConvention,
                                                                    PaymentFrequency,
                                                                    DayCountConvention)


class InterestRateSwapDirection(Enum):
    PAYER_FIXED = 0
    RECEIVER_FIXED = 1


class SwapAccrual(NamedTuple):
    start_accrual: date
    end_accrual: date
    accrual_factor: Optional[float] = None


@dataclass
class SwapPayment(Payment):
    fixing_date: Optional[date] = None


class TermInterestRateSwap(CashflowCollection):
    def __init__(self,
                 float_index: CurveIndex,
                 direction: InterestRateSwapDirection,
                 fixed_rate: float,
                 notional: int,
                 start_accrual_date: date,
                 end_accrual_date: date,
                 purchase_date: date,
                 floating_leg_payment_frequency: PaymentFrequency,
                 fixed_leg_payment_frequency: PaymentFrequency,
                 floating_leg_day_count_convention: DayCountConvention,
                 fixed_leg_day_count_convention: DayCountConvention,
                 holiday_calendar: dict[str, Holiday],
                 fixing_date_for_accrual_period: SettlementConvention = SettlementConvention.T_MINUS_TWO_BUSINESS,
                 payment_delay: SettlementConvention = SettlementConvention.T_PLUS_TWO_BUSINESS,
                 business_day_adjustment: BusinessDayAdjustment = BusinessDayAdjustment.MODIFIED_FOLLOWING
                 ) -> None:

        self._float_index = float_index
        self._direction = direction
        self._fixed_rate = fixed_rate
        self._notional = notional
        self._start_accrual_date = start_accrual_date
        self._end_accrual_date = end_accrual_date
        self._purchase_date = purchase_date
        self._floating_leg_payment_frequency = floating_leg_payment_frequency
        self._fixed_leg_payment_frequency = fixed_leg_payment_frequency
        self._floating_leg_day_count_convention = floating_leg_day_count_convention
        self._fixed_leg_day_count_convention = fixed_leg_day_count_convention
        self._holiday_calendar = holiday_calendar
        self._fixing_date_for_accrual_period = fixing_date_for_accrual_period
        self._payment_delay = payment_delay
        self._business_day_adjustment = business_day_adjustment
        self._date_adjustment_function = self.create_date_adjustment_function()

        cashflows = (None, None)

        cashflow_keys = (CashflowKeys.FIXED_LEG, CashflowKeys.FLOATING_LEG)
        super().__init__(cashflows=cashflows, cashflow_keys=cashflow_keys)

    @property
    def fixed_rate(self) -> float:
        return self._fixed_rate

    @property
    def direction(self) -> InterestRateSwapDirection:
        return self._direction

    @property
    def notional(self) -> int:
        return self._notional

    @property
    def start_accrual_date(self) -> date:
        return self._start_accrual_date

    @property
    def end_accrual_date(self) -> date:
        return self._end_accrual_date

    @property
    def purchase_date(self) -> date:
        return self._purchase_date

    @property
    def float_index(self) -> CurveIndex:
        return self._float_index

    @property
    def floating_leg(self) -> Cashflow:
        return self[CashflowKeys.FLOATING_LEG]

    @property
    def fixed_leg(self) -> Cashflow:
        return self[CashflowKeys.FIXED_LEG]

    @property
    def business_day_adjustment(self) -> BusinessDayAdjustment:
        return self._business_day_adjustment

    @property
    def holiday_calendar(self) -> dict[str, Holiday]:
        return self._holiday_calendar

    @property
    def fixing_date_for_accrual_period(self) -> SettlementConvention:
        return self._fixing_date_for_accrual_period

    @property
    def date_adjustment_function(self) -> Callable[[date], date]:
        return self._date_adjustment_function

    @property
    def floating_leg_payment_frequency(self) -> PaymentFrequency:
        return self._floating_leg_payment_frequency

    @property
    def fixed_leg_payment_frequency(self) -> PaymentFrequency:
        return self._fixed_leg_payment_frequency

    @property
    def floating_leg_day_count_convention(self) -> DayCountConvention:
        return self._floating_leg_day_count_convention

    @property
    def fixed_leg_day_count_convention(self) -> DayCountConvention:
        return self._fixed_leg_day_count_convention

    @property
    def payment_delay(self) -> SettlementConvention:
        return self._payment_delay

    # Interface Methods
    def to_knot_value_pair(self) -> KnotValuePair:
        pass

    def present_value(self, discount_curve: DiscountCurve, interes_rates: Callable[[date], float]) -> float:
        """

        """
        pass


    def create_date_adjustment_function(self) -> Callable[[date], date]:
        """
        Creates the date adjustment function for adjusting payment days which don't fall on
        a business day. The adjustment used is dictated by the BusinessDayAdjustment.
        """

        match self.business_day_adjustment:
            case BusinessDayAdjustment.FOLLOWING:
                return lambda date_obj: Scheduler.following_date_adjustment(date_obj,
                                                                            holiday_calendar=self.holiday_calendar)
            case BusinessDayAdjustment.MODIFIED_FOLLOWING:
                return lambda date_obj: Scheduler.modified_following_date_adjustment(date_obj,
                                                                                     holiday_calendar=self.holiday_calendar)
            case _:
                raise ValueError(f" Business day adjustment {self.business_day_adjustment} is invalid.")


    def generate_floating_leg_accrual_schedule(self) -> list[SwapAccrual]:
        """
        Returns
        """
        match self.floating_leg_payment_frequency:
            case PaymentFrequency.ANNUAL:
                increment = relativedelta(years=-1)

            case PaymentFrequency.SEMI_ANNUAL:
                increment = relativedelta(months=-6)

            case PaymentFrequency.QUARTERLY:
                increment = relativedelta(months=-3)

            case _:
                raise ValueError(f'Payment Frequency {self.floating_leg_payment_frequency} is not valid to generate a floating leg payment schedule.')

        unadjusted_accrual_dates = Scheduler.generate_dates_by_increments(start_date=self.end_accrual_date,
                                                                          end_date=self.start_accrual_date,
                                                                          increment=increment)
        unadjusted_accrual_dates.reverse()
        adjusted_accrual_dates = [self.date_adjustment_function(accrual_date) for accrual_date in unadjusted_accrual_dates]
        swap_accruals = []

        for start_accrual, end_accrual in itertools.pairwise(adjusted_accrual_dates):
            accrual = DayCountCalculator.compute_accrual_length(start_accrual,
                                                                end_accrual,
                                                                self.floating_leg_day_count_convention)

            swap_accrual = SwapAccrual(start_accrual=start_accrual,
                                       end_accrual=end_accrual,
                                       accrual_factor=accrual)

            swap_accruals.append(swap_accrual)

        return swap_accruals

    def generate_fixed_leg_accrual_schedule(self) -> list[SwapAccrual]:
        """
        Generates a list of all fixed leg accruals
        """

        match self.fixed_leg_payment_frequency:
            case PaymentFrequency.ANNUAL:
                increment = relativedelta(years=-1)

            case PaymentFrequency.SEMI_ANNUAL:
                increment = relativedelta(months=-6)

            case PaymentFrequency.QUARTERLY:
                increment = relativedelta(months=-3)
            case _:
                raise ValueError(
                    f'Payment Frequency {self.fixed_leg_payment_frequency} is not valid to generate a floating leg payment schedule.')

        unadjusted_accrual_dates = Scheduler.generate_dates_by_increments(start_date=self.end_accrual_date,
                                                                          end_date=self.start_accrual_date,
                                                                          increment=increment)
        unadjusted_accrual_dates.reverse()
        adjusted_accrual_dates = [self.date_adjustment_function(accrual_date) for accrual_date in unadjusted_accrual_dates]
        fixed_leg_accruals = []

        for start_accrual, end_accrual in itertools.pairwise(adjusted_accrual_dates):
            accrual = DayCountCalculator.compute_accrual_length(start_accrual,
                                                                end_accrual,
                                                                self.fixed_leg_day_count_convention)

            fixed_leg_accruals.append(SwapAccrual(start_accrual=start_accrual,
                                                  end_accrual=end_accrual,
                                                  accrual_factor=accrual))

        return fixed_leg_accruals

    def create_floating_leg_cashflow(self, interest_rate: Callable[[date], float]) -> Cashflow:
        """
        Creates a cashflow of fixed leg payments from the provided interest rate curve, which
        is assumed to be the

        The interest_rate argument is assumed to be a general callable object which maps dates to
        floats representing interest rates. These could be either forward rates from a curve
        or short rates from a short rate model.
        """

        floating_leg_accruals = self.generate_floating_leg_accrual_schedule()
        floating_payments = []

        for accrual in floating_leg_accruals:
            fixing_date = Scheduler.calculate_settlement_date(accrual.start_accrual,
                                                              self.fixing_date_for_accrual_period,
                                                              self.holiday_calendar)

            interest_rate_fixing = interest_rate(fixing_date)

            payment_date = Scheduler.calculate_settlement_date(accrual.end_accrual,
                                                               self.payment_delay,
                                                               self.holiday_calendar)

            payment_amount = accrual.accrual_factor * self.notional * interest_rate_fixing

            payment = SwapPayment(payment_date=payment_date, payment=payment_amount, fixing_date=fixing_date)

            floating_payments.append(payment)

        return Cashflow(floating_payments)

    def create_fixed_leg_cashflow(self) -> Cashflow:
        """

        """
        fixed_leg_accruals = self.generate_fixed_leg_accrual_schedule()
        fixed_payments = []

        for accrual in fixed_leg_accruals:
            payment_amount = accrual.accrual_factor * self.notional * self.fixed_rate
            payment_date = Scheduler.calculate_settlement_date(accrual.end_accrual,
                                                               self.payment_delay,
                                                               self.holiday_calendar)

            payment = SwapPayment(payment_date=payment_date, payment=payment_amount, fixing_date=None)
            fixed_payments.append(payment)

        return Cashflow(fixed_payments)




class OvernightIndexSwap:
    def __init__(self):
        pass


#---------------------------------------------------------------------------

if __name__ == '__main__':
    from fixedIncome.src.scheduling_tools.holidays import US_FEDERAL_HOLIDAYS

    test_libor_swap = TermInterestRateSwap(
        float_index=CurveIndex.LIBOR_3M,
        direction=InterestRateSwapDirection.RECEIVER_FIXED,
        fixed_rate=0.055,
        notional=1_000_000,
        start_accrual_date=date(2024, 1, 1),
        end_accrual_date=date(2034, 1, 1),
        purchase_date=date(2024, 1, 1),
        floating_leg_payment_frequency=PaymentFrequency.SEMI_ANNUAL,
        fixed_leg_payment_frequency=PaymentFrequency.QUARTERLY,
        floating_leg_day_count_convention=DayCountConvention.ACTUAL_OVER_360,
        fixed_leg_day_count_convention=DayCountConvention.THIRTY_OVER_THREESIXTY,
        holiday_calendar=US_FEDERAL_HOLIDAYS,
        payment_delay=SettlementConvention.T_PLUS_ZERO_BUSINESS,
        business_day_adjustment=BusinessDayAdjustment.MODIFIED_FOLLOWING
    )

    test_libor_swap.generate_fixed_leg_accrual_schedule()
    test_libor_swap.generate_floating_leg_accrual_schedule()

