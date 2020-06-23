"""Custom pandas accessors.

!!! note
    Input arrays must be `numpy.bool`.
    
```py
import vectorbt as vbt
import numpy as np
import pandas as pd
from numba import njit
from datetime import datetime

index = pd.Index([
    datetime(2020, 1, 1),
    datetime(2020, 1, 2),
    datetime(2020, 1, 3),
    datetime(2020, 1, 4),
    datetime(2020, 1, 5)
])
columns = ['a', 'b', 'c']
signals = pd.DataFrame([
    [False, True, True],
    [True, False, True],
    [True, True, False],
    [False, True, True],
    [True, False, True]
], index=index, columns=columns)
ts = pd.DataFrame([
    [1, 5, 1],
    [2, 4, 2],
    [3, 3, 3],
    [4, 2, 2],
    [5, 1, 1]
], index=index, columns=columns)
```"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from vectorbt.defaults import color_schema, contrast_color_schema
from vectorbt.accessors import register_dataframe_accessor, register_series_accessor
from vectorbt.utils import checks, reshape_fns, index_fns
from vectorbt.utils.config import merge_kwargs
from vectorbt.utils.decorators import add_nb_methods, cached_property
from vectorbt.utils.colors import adjust_lightness
from vectorbt.timeseries.accessors import TimeSeries_Accessor, TimeSeries_SRAccessor, TimeSeries_DFAccessor
from vectorbt.signals import nb
from vectorbt.widgets import DefaultFigureWidget


@add_nb_methods(
    nb.shuffle_nb,
    nb.fshift_nb,
    module_name='vectorbt.signals.nb')
class Signals_Accessor(TimeSeries_Accessor):
    """Accessor on top of signal series. For both, Series and DataFrames.

    Accessible through `pandas.Series.vbt.signals` and `pandas.DataFrame.vbt.signals`."""

    def __init__(self, obj, freq=None):
        if not checks.is_pandas(obj):  # parent accessor
            obj = obj._obj

        checks.assert_dtype(obj, np.bool)

        TimeSeries_Accessor.__init__(self, obj, freq=freq)

    @classmethod
    def empty(cls, *args, fill_value=False, **kwargs):
        """`vectorbt.utils.accessors.Base_Accessor.empty` with `fill_value=False`.

        Example:
            ```python-repl
            >>> print(pd.DataFrame.vbt.signals.empty((5, 3), 
            ...     index=index, columns=columns))
                            a      b      c
            2020-01-01  False  False  False
            2020-01-02  False  False  False
            2020-01-03  False  False  False
            2020-01-04  False  False  False
            2020-01-05  False  False  False
            ```"""
        return TimeSeries_Accessor.empty(*args, fill_value=fill_value, **kwargs)

    @classmethod
    def empty_like(cls, *args, fill_value=False, **kwargs):
        """`vectorbt.utils.accessors.Base_Accessor.empty_like` with `fill_value=False`.

        Example:
            ```python-repl
            >>> print(pd.DataFrame.vbt.signals.empty_like(signals))
                            a      b      c
            2020-01-01  False  False  False
            2020-01-02  False  False  False
            2020-01-03  False  False  False
            2020-01-04  False  False  False
            2020-01-05  False  False  False
            ```"""
        return TimeSeries_Accessor.empty_like(*args, fill_value=fill_value, **kwargs)

    @classmethod
    def generate(cls, shape, choice_func_nb, *args, **kwargs):
        """See `vectorbt.signals.nb.generate_nb`.

        `**kwargs` will be passed to pandas constructor.

        Example:
            Generate random signals manually:

            ```python-repl
            >>> @njit
            ... def choice_func_nb(col, from_i, to_i):
            ...     return np.random.choice(np.arange(from_i, to_i), replace=False)

            >>> print(pd.DataFrame.vbt.signals.generate((5, 3), 
            ...     choice_func_nb, index=index, columns=columns))
                            a      b      c
            2020-01-01  False  False  False
            2020-01-02  False  False  False
            2020-01-03   True  False   True
            2020-01-04  False  False  False
            2020-01-05  False   True  False
            ```"""
        checks.assert_numba_func(choice_func_nb)

        if not isinstance(shape, tuple):
            shape = (shape, 1)
        elif isinstance(shape, tuple) and len(shape) == 1:
            shape = (shape[0], 1)

        result = nb.generate_nb(shape, choice_func_nb, *args)

        if cls.is_series():
            return pd.Series(result[:, 0], **kwargs)
        return pd.DataFrame(result, **kwargs)

    @classmethod
    def generate_random(cls, shape, n_range, n_prob=None, min_space=None, seed=None, **kwargs):
        """See `vectorbt.signals.nb.generate_random_nb`.

        `**kwargs` will be passed to pandas constructor.

        Example:
            For each column, generate either 1 (with 30% probability) or 2 (with 70% probability)
            signals randomly. Leave one position free between signals:

            ```python-repl
            >>> print(pd.DataFrame.vbt.signals.generate_random((5, 3), [1, 2], 
            ...     n_prob=[0.3, 0.7], min_space=1, seed=42, index=index, columns=columns))
                            a      b      c
            2020-01-01   True  False  False
            2020-01-02  False   True  False
            2020-01-03   True  False  False
            2020-01-04  False   True   True
            2020-01-05  False  False  False
            ```"""
        if not isinstance(shape, tuple):
            shape = (shape, 1)
        elif isinstance(shape, tuple) and len(shape) == 1:
            shape = (shape[0], 1)

        n_range = reshape_fns.to_1d(n_range)
        if n_prob is not None:
            n_prob = reshape_fns.to_1d(n_prob)
            checks.assert_same_shape(n_range, n_prob)
        result = nb.generate_random_nb(shape, n_range, n_prob=n_prob, min_space=min_space, seed=seed)

        if cls.is_series():
            return pd.Series(result[:, 0], **kwargs)
        return pd.DataFrame(result, **kwargs)

    @classmethod
    def generate_iteratively(cls, shape, choice_func1_nb, choice_func2_nb, *args, **kwargs):
        """See `vectorbt.signals.nb.generate_iteratively_nb`.

        `**kwargs` will be passed to pandas constructor.

        Example:
            Generate entry and exit signals one after another:

            ```python-repl
            >>> @njit
            ... def choice_func1_nb(col, from_i, to_i):
            ...     return np.array([from_i])
            >>> @njit
            ... def choice_func2_nb(col, from_i, to_i):
            ...     return np.array([from_i])

            >>> entries, exits = pd.DataFrame.vbt.signals.generate_iteratively(
            ...     (5, 3), choice_func1_nb, choice_func2_nb, 
            ...     index=index, columns=columns)
            >>> print(entries)
                            a      b      c
            2020-01-01   True   True   True
            2020-01-02  False  False  False
            2020-01-03   True   True   True
            2020-01-04  False  False  False
            2020-01-05   True   True   True
            >>> print(exits)
                            a      b      c
            2020-01-01  False  False  False
            2020-01-02   True   True   True
            2020-01-03  False  False  False
            2020-01-04   True   True   True
            2020-01-05  False  False  False
            ```"""
        checks.assert_numba_func(choice_func1_nb)
        checks.assert_numba_func(choice_func2_nb)

        if not isinstance(shape, tuple):
            shape = (shape, 1)
        elif isinstance(shape, tuple) and len(shape) == 1:
            shape = (shape[0], 1)

        result1, result2 = nb.generate_iteratively_nb(shape, choice_func1_nb, choice_func2_nb, *args)
        if cls.is_series():
            return pd.Series(result1[:, 0], **kwargs), pd.Series(result2[:, 0], **kwargs)
        return pd.DataFrame(result1, **kwargs), pd.DataFrame(result2, **kwargs)

    def generate_after(self, choice_func_nb, *args):
        """See `vectorbt.signals.nb.generate_after_nb`.

        Example:
            Fill all space between signals in `signals`:

            ```python-repl
            >>> @njit
            ... def choice_func_nb(col, from_i, to_i):
            ...     return np.arange(from_i, to_i)

            >>> print(signals.vbt.signals.generate_after(choice_func_nb))
                            a      b      c
            2020-01-01  False  False  False
            2020-01-02  False   True  False
            2020-01-03  False  False   True
            2020-01-04   True  False  False
            2020-01-05  False   True  False
            ```"""
        checks.assert_numba_func(choice_func_nb)

        return self.wrap(nb.generate_after_nb(self.to_2d_array(), choice_func_nb, *args))

    def generate_random_after(self, n_range, n_prob=None, min_space=None, seed=None):
        """See `vectorbt.signals.nb.generate_random_after_nb`.

        Example:
            Generate exactly one random signal after each signal in `signals`:

            ```python-repl
            >>> print(signals.vbt.signals.generate_random_after(1, seed=42))
                            a      b      c
            2020-01-01  False  False  False
            2020-01-02  False   True  False
            2020-01-03  False  False   True
            2020-01-04   True  False  False
            2020-01-05  False   True  False
            ```"""
        n_range = reshape_fns.to_1d(n_range)
        if n_prob is not None:
            n_prob = reshape_fns.to_1d(n_prob)
            checks.assert_same_shape(n_range, n_prob)
        result = nb.generate_random_after_nb(
            self.to_2d_array(), n_range, n_prob=n_prob, min_space=min_space, seed=seed)
        return self.wrap(result)

    def generate_stop_loss(self, ts, stops, trailing=False, relative=True,
                           first=True, as_columns=None, broadcast_kwargs={}):
        """See `vectorbt.signals.nb.generate_stop_loss_nb`.

        Arguments will be broadcasted using `vectorbt.utils.reshape_fns.broadcast`
        with `broadcast_kwargs`. Argument `stops` can be either a single number, an array of 
        numbers, or a 3D array, where each matrix corresponds to a single configuration. 
        Use `as_columns` as a top-level column level.

        Example:
            For each entry in `signals`, set stop loss for 10% and 20% below the price `ts`:

            ```python-repl
            >>> print(signals.vbt.signals.generate_stop_loss(ts, [0.1, 0.2]))
            stop_loss                   0.1                  0.2
                            a      b      c      a      b      c
            2020-01-01  False  False  False  False  False  False
            2020-01-02  False   True  False  False   True  False
            2020-01-03  False  False  False  False  False  False
            2020-01-04  False  False  False  False  False  False
            2020-01-05  False   True  False  False   True  False
            ```"""
        entries = self._obj
        checks.assert_type(ts, (pd.Series, pd.DataFrame))

        entries, ts = reshape_fns.broadcast(entries, ts, **broadcast_kwargs, writeable=True)
        stops = reshape_fns.broadcast_to_array_of(stops, entries.vbt.to_2d_array())
        exits = nb.generate_stop_loss_nb(
            entries.vbt.to_2d_array(), 
            ts.vbt.to_2d_array(), 
            stops,
            trailing=trailing,
            relative=relative,
            first=first)

        # Build column hierarchy
        if as_columns is not None:
            param_columns = as_columns
        else:
            name = 'trail_stop' if trailing else 'stop_loss'
            param_columns = index_fns.index_from_values(stops, name=name)
        columns = index_fns.combine_indexes(param_columns, entries.vbt.columns)
        return entries.vbt.wrap(exits, columns=columns)

    def generate_take_profit(self, ts, stops, relative=True, first=True, as_columns=None, broadcast_kwargs={}):
        """See `vectorbt.signals.nb.generate_take_profit_nb`.

        Arguments will be broadcasted using `vectorbt.utils.reshape_fns.broadcast`
        with `broadcast_kwargs`. Argument `stops` can be either a single number, an array of 
        numbers, or a 3D array, where each matrix corresponds to a single configuration. 
        Use `as_columns` as a top-level column level.

        Example:
            For each entry in `signals`, set take profit for 10% and 20% above the price `ts`:

            ```python-repl
            >>> print(signals.vbt.signals.generate_take_profit(ts, [0.1, 0.2]))
            take_profit                  0.1                  0.2
                             a      b      c      a      b      c
            2020-01-01   False  False  False  False  False  False
            2020-01-02   False  False  False  False  False  False
            2020-01-03   False  False   True  False  False   True
            2020-01-04    True  False  False   True  False  False
            2020-01-05   False  False  False  False  False  False
            ```"""
        entries = self._obj
        checks.assert_type(ts, (pd.Series, pd.DataFrame))

        entries, ts = reshape_fns.broadcast(entries, ts, **broadcast_kwargs, writeable=True)
        stops = reshape_fns.broadcast_to_array_of(stops, entries.vbt.to_2d_array())
        exits = nb.generate_take_profit_nb(
            entries.vbt.to_2d_array(), 
            ts.vbt.to_2d_array(),
            stops,
            relative=relative,
            first=first)

        # Build column hierarchy
        if as_columns is not None:
            param_columns = as_columns
        else:
            param_columns = index_fns.index_from_values(stops, name='take_profit')
        columns = index_fns.combine_indexes(param_columns, entries.vbt.columns)
        return entries.vbt.wrap(exits, columns=columns)

    def map_reduce_between(self, *args, other=None, map_func_nb=None, reduce_func_nb=None, broadcast_kwargs={}):
        """See `vectorbt.signals.nb.map_reduce_between_nb`. 

        If `other` specified, see `vectorbt.signals.nb.map_reduce_between_two_nb`.

        Arguments will be broadcasted using `vectorbt.utils.reshape_fns.broadcast`
        with `broadcast_kwargs`.

        Example:
            Get average distance between signals in `signals`:

            ```python-repl
            >>> distance_map_nb = njit(lambda col, from_i, to_i: to_i - from_i)
            >>> mean_reduce_nb = njit(lambda col, a: np.nanmean(a))

            >>> print(signals.vbt.signals.map_reduce_between(
            ...     map_func_nb=distance_map_nb, reduce_func_nb=mean_reduce_nb))
            a    1.500000
            b    1.500000
            c    1.333333
            dtype: float64
            ```"""
        checks.assert_not_none(map_func_nb)
        checks.assert_not_none(reduce_func_nb)
        checks.assert_numba_func(map_func_nb)
        checks.assert_numba_func(reduce_func_nb)

        if other is None:
            # One input array
            result = nb.map_reduce_between_nb(self.to_2d_array(), map_func_nb, reduce_func_nb, *args)
            if isinstance(self._obj, pd.Series):
                return result[0]
            return pd.Series(result, index=self.columns)
        else:
            # Two input arrays
            obj, other = reshape_fns.broadcast(self._obj, other, **broadcast_kwargs)
            checks.assert_dtype(other, np.bool_)
            result = nb.map_reduce_between_two_nb(
                self.to_2d_array(), other.vbt.to_2d_array(), map_func_nb, reduce_func_nb, *args)
            return self.wrap_reduced(result)


    def map_reduce_partitions(self, *args, map_func_nb=None, reduce_func_nb=None):
        """See `vectorbt.signals.nb.map_reduce_partitions_nb`.

        Example:
            Get average length of each partition in `signals`:

            ```python-repl
            >>> distance_map_nb = njit(lambda col, from_i, to_i: to_i - from_i)
            >>> mean_reduce_nb = njit(lambda col, a: np.nanmean(a))

            >>> print(signals.vbt.signals.map_reduce_partitions(
            ...     map_func_nb=distance_map_nb, reduce_func_nb=mean_reduce_nb))
            a    1.5
            b    1.5
            c    2.0
            dtype: float64
            ```"""
        checks.assert_not_none(map_func_nb)
        checks.assert_not_none(reduce_func_nb)
        checks.assert_numba_func(map_func_nb)
        checks.assert_numba_func(reduce_func_nb)

        result = nb.map_reduce_partitions_nb(self.to_2d_array(), map_func_nb, reduce_func_nb, *args)
        return self.wrap_reduced(result)

    @cached_property
    def num_signals(self):
        """Sum up `True` values."""
        return self.wrap_reduced(self._obj.values.sum(axis=0))

    @cached_property
    def avg_distance(self):
        """Calculate the average distance between `True` values.

        See `Signals_Accessor.map_reduce_between`."""
        return self.map_reduce_between(
            map_func_nb=nb.distance_map_nb, reduce_func_nb=nb.mean_reduce_nb)

    def avg_distance_to(self, other, **kwargs):
        """Calculate the average distance between `True` values in `self` and `other`.

        See `Signals_Accessor.map_reduce_between`."""
        return self.map_reduce_between(
            other=other, map_func_nb=nb.distance_map_nb, reduce_func_nb=nb.mean_reduce_nb, **kwargs)

    def rank(self, reset_by=None, after_false=False, allow_gaps=False, broadcast_kwargs={}):
        """See `vectorbt.signals.nb.rank_nb`.

        Example:
            Rank each `True` value in each partition in `signals`:

            ```python-repl
            >>> print(signals.vbt.signals.rank())
                        a  b  c
            2020-01-01  0  1  1
            2020-01-02  1  0  2
            2020-01-03  2  1  0
            2020-01-04  0  2  1
            2020-01-05  1  0  2
            >>> print(signals.vbt.signals.rank(after_false=True))
                        a  b  c
            2020-01-01  0  0  0
            2020-01-02  1  0  0
            2020-01-03  2  1  0
            2020-01-04  0  2  1
            2020-01-05  1  0  2
            >>> print(signals.vbt.signals.rank(allow_gaps=True))
                        a  b  c
            2020-01-01  0  1  1
            2020-01-02  1  0  2
            2020-01-03  2  2  0
            2020-01-04  0  3  3
            2020-01-05  3  0  4
            >>> print(signals.vbt.signals.rank(reset_by=~signals, allow_gaps=True))
                        a  b  c
            2020-01-01  0  1  1
            2020-01-02  1  0  2
            2020-01-03  2  1  0
            2020-01-04  0  2  1
            2020-01-05  1  0  2
            ```"""
        if reset_by is not None:
            obj, reset_by = reshape_fns.broadcast(self._obj, reset_by, **broadcast_kwargs)
            reset_by = reset_by.vbt.to_2d_array()
        else:
            obj = self._obj
        ranked = nb.rank_nb(
            obj.vbt.to_2d_array(),
            reset_by=reset_by,
            after_false=after_false,
            allow_gaps=allow_gaps)
        return obj.vbt.wrap(ranked)

    def rank_partitions(self, reset_by=None, after_false=False, broadcast_kwargs={}):
        """See `vectorbt.signals.nb.rank_partitions_nb`.

        Example:
            Rank each partition of `True` values in `signals`:

            ```python-repl
            >>> print(signals.vbt.signals.rank_partitions())
                        a  b  c
            2020-01-01  0  1  1
            2020-01-02  1  0  1
            2020-01-03  1  2  0
            2020-01-04  0  2  2
            2020-01-05  2  0  2
            >>> print(signals.vbt.signals.rank_partitions(after_false=True))
                        a  b  c
            2020-01-01  0  0  0
            2020-01-02  1  0  0
            2020-01-03  1  1  0
            2020-01-04  0  1  1
            2020-01-05  2  0  1
            >>> print(signals.vbt.signals.rank_partitions(reset_by=signals))
                        a  b  c
            2020-01-01  0  1  1
            2020-01-02  1  0  1
            2020-01-03  1  1  0
            2020-01-04  0  1  1
            2020-01-05  1  0  1
            ```"""
        if reset_by is not None:
            obj, reset_by = reshape_fns.broadcast(self._obj, reset_by, **broadcast_kwargs)
            reset_by = reset_by.vbt.to_2d_array()
        else:
            obj = self._obj
        ranked = nb.rank_partitions_nb(
            obj.vbt.to_2d_array(),
            reset_by=reset_by,
            after_false=after_false)
        return obj.vbt.wrap(ranked)

    def first(self, **kwargs):
        """`vectorbt.signals.nb.rank_nb` == 1."""
        return self.wrap(self.rank(**kwargs).values == 1)

    def nst(self, n, **kwargs):
        """`vectorbt.signals.nb.rank_nb` == n."""
        return self.wrap(self.rank(**kwargs).values == n)

    def from_nst(self, n, **kwargs):
        """`vectorbt.signals.nb.rank_nb` >= n."""
        return self.wrap(self.rank(**kwargs).values >= n)

    def AND(self, *others, **kwargs):
        """Combine with each in `*others` using logical AND.

        See `vectorbt.utils.accessors.Base_Accessor.combine_with_multiple`.

        """
        return self.combine_with_multiple(others, combine_func=np.logical_and, **kwargs)

    def OR(self, *others, **kwargs):
        """Combine with each in `*others` using logical OR.

        See `vectorbt.utils.accessors.Base_Accessor.combine_with_multiple`.

        Example:
            Perform two OR operations and concatenate them:

            ```python-repl
            >>> print(signals.vbt.signals.OR(ts > 1, ts > 2, 
            ...     concat=True, as_columns=['>1', '>2']))
                                        >1                  >2
                            a      b     c      a      b     c
            2020-01-01  False   True  True  False   True  True
            2020-01-02   True   True  True   True   True  True
            2020-01-03   True   True  True   True   True  True
            2020-01-04   True   True  True   True   True  True
            2020-01-05   True  False  True   True  False  True
            ```"""
        return self.combine_with_multiple(others, combine_func=np.logical_or, **kwargs)

    def XOR(self, *others, **kwargs):
        """Combine with each in `*others` using logical XOR.

        See `vectorbt.utils.accessors.Base_Accessor.combine_with_multiple`."""
        return self.combine_with_multiple(others, combine_func=np.logical_xor, **kwargs)


@register_series_accessor('signals')
class Signals_SRAccessor(Signals_Accessor, TimeSeries_SRAccessor):
    """Accessor on top of signal series. For Series only.

    Accessible through `pandas.Series.vbt.signals`."""

    def __init__(self, obj, freq=None):
        if not checks.is_pandas(obj):  # parent accessor
            obj = obj._obj

        TimeSeries_SRAccessor.__init__(self, obj, freq=freq)
        Signals_Accessor.__init__(self, obj, freq=freq)

    def plot(self, name=None, trace_kwargs={}, fig=None, **layout_kwargs):
        """Plot Series as a line.

        Args:
            name (str): Name of the signals.
            trace_kwargs (dict): Keyword arguments passed to `plotly.graph_objects.Scatter`.
            fig (plotly.graph_objects.Figure): Figure to add traces to.
            **layout_kwargs: Keyword arguments for layout.
        Example:
            ```py
            signals['a'].vbt.signals.plot()
            ```

            ![](/vectorbt/docs/img/signals_sr_plot.png)"""
        # Set up figure
        if fig is None:
            fig = DefaultFigureWidget()
        fig.update_layout(
            yaxis=dict(
                tickmode='array',
                tickvals=[0, 1],
                ticktext=['false', 'true']
            )
        )
        fig.update_layout(**layout_kwargs)
        if name is None:
            name = self._obj.name

        scatter = go.Scatter(
            x=self.index,
            y=self._obj.values,
            mode='lines',
            name=str(name),
            showlegend=name is not None
        )
        scatter.update(**trace_kwargs)
        fig.add_trace(scatter)

        return fig

    def plot_as_markers(self, ts, name=None, trace_kwargs={}, fig=None, **layout_kwargs):
        """Plot Series as markers.

        Args:
            ts (pandas.Series): Time series to plot markers on.

                !!! note
                    Doesn't plot `ts`.

            name (str): Name of the signals.
            trace_kwargs (dict): Keyword arguments passed to `plotly.graph_objects.Scatter`.
            fig (plotly.graph_objects.Figure): Figure to add traces to.
            **layout_kwargs: Keyword arguments for layout.
        Example:
            ```py
            fig = ts['a'].vbt.timeseries.plot()
            signals['a'].vbt.signals.plot_as_entry_markers(ts['a'], fig=fig)
            (~signals['a']).vbt.signals.plot_as_exit_markers(ts['a'], fig=fig)
            ```

            ![](/vectorbt/docs/img/signals_plot_as_markers.png)"""
        checks.assert_type(ts, pd.Series)
        checks.assert_same_index(self._obj, ts)

        if fig is None:
            fig = DefaultFigureWidget()
        fig.update_layout(**layout_kwargs)
        if name is None:
            name = self._obj.name

        # Plot markers
        scatter = go.Scatter(
            x=ts.index[self._obj],
            y=ts[self._obj],
            mode='markers',
            marker=dict(
                symbol='circle',
                color=contrast_color_schema['blue'],
                size=7,
                line=dict(
                    width=1,
                    color=adjust_lightness(contrast_color_schema['blue'])
                )
            ),
            name=str(name),
            showlegend=name is not None
        )
        scatter.update(**trace_kwargs)
        fig.add_trace(scatter)
        return fig

    def plot_as_entry_markers(self, *args, name='Entry', trace_kwargs={}, **kwargs):
        """Plot signals as entry markers.
        
        See `Signals_SRAccessor.plot_as_markers`."""
        trace_kwargs = merge_kwargs(dict(
            marker=dict(
                symbol='circle',
                color=contrast_color_schema['green'],
                size=7,
                line=dict(
                    width=1,
                    color=adjust_lightness(contrast_color_schema['green'])
                )
            )
        ), trace_kwargs)
        return self.plot_as_markers(*args, name=name, trace_kwargs=trace_kwargs, **kwargs)

    def plot_as_exit_markers(self, *args, name='Exit', trace_kwargs={}, **kwargs):
        """Plot signals as exit markers.
        
        See `Signals_SRAccessor.plot_as_markers`."""
        trace_kwargs = merge_kwargs(dict(
            marker=dict(
                symbol='circle',
                color=contrast_color_schema['orange'],
                size=7,
                line=dict(
                    width=1,
                    color=adjust_lightness(contrast_color_schema['orange'])
                )
            )
        ), trace_kwargs)
        return self.plot_as_markers(*args, name=name, trace_kwargs=trace_kwargs, **kwargs)


@register_dataframe_accessor('signals')
class Signals_DFAccessor(Signals_Accessor, TimeSeries_DFAccessor):
    """Accessor on top of signal series. For DataFrames only.

    Accessible through `pandas.DataFrame.vbt.signals`."""

    def __init__(self, obj, freq=None):
        if not checks.is_pandas(obj):  # parent accessor
            obj = obj._obj

        TimeSeries_DFAccessor.__init__(self, obj, freq=freq)
        Signals_Accessor.__init__(self, obj, freq=freq)

    def plot(self, trace_kwargs={}, fig=None, **layout_kwargs):
        """Plot each column in DataFrame as a line.

        Args:
            trace_kwargs (dict or list of dict): Keyword arguments passed to each `plotly.graph_objects.Scatter`.
            fig (plotly.graph_objects.Figure): Figure to add traces to.
            **layout_kwargs: Keyword arguments for layout.
        Example:
            ```py
            signals[['a', 'c']].vbt.signals.plot().show_png()
            ```

            ![](/vectorbt/docs/img/signals_signals_plot.png)"""
        for col in range(self._obj.shape[1]):
            fig = self._obj.iloc[:, col].vbt.signals.plot(
                trace_kwargs=trace_kwargs,
                fig=fig,
                **layout_kwargs
            )

        return fig
