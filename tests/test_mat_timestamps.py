"""Optional acquisition metadata cannot reject otherwise valid MAT recordings."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
import warnings
import numpy as np
from scipy.io import savemat
from opencaliper import load
from opencaliper.acquisition import timestamp


class MatTimestampTests(unittest.TestCase):
    def test_recognized_values_are_retained(self):
        cases=[({'date':'2024-05-03','time':'09:53:31'},datetime(2024,5,3,9,53,31)),
               ({'date':'202453','time':'95331'},datetime(2024,5,3,9,53,31)),
               ({'recording_timestamp':'2024-05-03T09:53:31Z'},datetime(2024,5,3,9,53,31,tzinfo=timezone.utc)),
               ({'recording_timestamp':'bad','date':'2024-05-03','time':'09:53:31'},datetime(2024,5,3,9,53,31))]
        for metadata,expected in cases:
            with self.subTest(metadata=metadata): self.assertEqual(timestamp(metadata),expected)

    def test_missing_unknown_and_ambiguous_metadata_is_quiet(self):
        cases=[{}, {'date':'2024-05-03'}, {'time':'09:53:31'},
               {'date':'2024111','time':'12345'}, {'date':'different format','time':'bad'},
               {'date':np.array([1,2]),'time':'12:00:00'},
               {'recording_timestamp':np.array([1,2])}, {'recording_timestamp':'not a date'},
               {'recording_timestamp':np.array([],dtype=float)}]
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            for metadata in cases:
                with self.subTest(metadata=metadata): self.assertEqual(timestamp(metadata),datetime(1970,1,1))

    def test_all_mat_layouts_load_with_unrecognized_metadata(self):
        layouts=[dict(points=4,xinc=.1,xorg=0,xref=0,Channel1_t1=np.arange(4,dtype=float),Channel1_unit='V'),
                 dict(signal_0_name='Native',signal_0_unit='V',signal_0_time=np.arange(4),signal_0_values=np.arange(4)),
                 dict(freq=np.arange(4)*1e6,peak=np.arange(4,dtype=float))]
        with tempfile.TemporaryDirectory() as folder, warnings.catch_warnings():
            warnings.simplefilter('error')
            for i,layout in enumerate(layouts):
                for metadata in ({},{'date':'unknown','time':'unsupported'}, {'recording_timestamp':np.array([1,2])}):
                    path=Path(folder)/f'layout{i}.mat'
                    savemat(path,{**layout,**metadata})
                    recording=load(path)
                    self.assertEqual(len(recording.signals),1)
                    self.assertEqual(recording.timestamp,datetime(1970,1,1))
