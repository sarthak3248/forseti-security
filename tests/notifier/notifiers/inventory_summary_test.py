# Copyright 2017 The Forseti Security Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests the GCS inventory summary upload notifier."""


import unittest.mock as mock
import unittest

from datetime import datetime

from google.cloud.forseti.common.util import errors as util_errors
from google.cloud.forseti.common.util import string_formats
from google.cloud.forseti.notifier.notifiers import base_notification
from google.cloud.forseti.notifier.notifiers import inventory_summary
from tests.unittest_utils import ForsetiTestCase


class InventorySummaryTest(ForsetiTestCase):
    """Tests for inventory_summary_notifier."""

    def setUp(self):
        """Setup."""
        ForsetiTestCase.setUp(self)
        self.fake_utcnow = datetime(year=1920, month=5, day=6, hour=7, minute=8)

    def tearDown(self):
        """Tear down method."""
        ForsetiTestCase.tearDown(self)

    @mock.patch(
        'google.cloud.forseti.notifier.notifiers.inventory_summary.date_time',
        autospec=True)
    def test_get_output_filename(self, mock_date_time):
        """Test_get_output_filename()."""
        # arrange
        mock_date_time.get_utc_now_datetime = mock.MagicMock()
        mock_date_time.get_utc_now_datetime.return_value = self.fake_utcnow

        mock_service_config = mock.MagicMock()
        mock_service_config.get_notifier_config.return_value = {}

        expected_timestamp = self.fake_utcnow.strftime(
            string_formats.TIMESTAMP_TIMEZONE_FILES)

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock.MagicMock())
        actual_filename = notifier._get_output_filename(
            string_formats.INVENTORY_SUMMARY_CSV_FMT)

        # assert
        expected_filename = string_formats.INVENTORY_SUMMARY_CSV_FMT.format(
                notifier.inventory_index_id, expected_timestamp)
        self.assertEqual(expected_filename, actual_filename)

    @mock.patch(
        'google.cloud.forseti.notifier.notifiers.inventory_summary.date_time',
        autospec=True)
    def test_get_output_filename_with_json(self, mock_date_time):
        """Test_get_output_filename()."""
        # arrange
        mock_date_time.get_utc_now_datetime = mock.MagicMock()
        mock_date_time.get_utc_now_datetime.return_value = self.fake_utcnow
        mock_service_config = mock.MagicMock()
        mock_service_config.get_notifier_config.return_value = {}
        
        expected_timestamp = self.fake_utcnow.strftime(
            string_formats.TIMESTAMP_TIMEZONE_FILES)

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock.MagicMock())
        actual_filename = notifier._get_output_filename(
            string_formats.INVENTORY_SUMMARY_JSON_FMT)

        # assert
        expected_filename = string_formats.INVENTORY_SUMMARY_JSON_FMT.format(
                notifier.inventory_index_id, expected_timestamp)
        self.assertEqual(expected_filename, actual_filename)

    @mock.patch(
        'google.cloud.forseti.common.util.file_uploader.StorageClient',
        autospec=True)
    @mock.patch('tempfile.NamedTemporaryFile')
    def test_upload_to_gcs_with_csv(self, mock_tempfile, mock_storage):
        """Test run()."""
        # arrange
        fake_tmpname = 'tmp_name'
        fake_output_name = 'abc'
        mock_service_config = mock.MagicMock()
        mock_service_config.get_notifier_config.return_value = {
            'inventory': {'gcs_summary': {'enabled': True,
                                          'data_format': 'csv',
                                          'gcs_path': 'gs://abcd'}}}
        mock_progess_queue = mock.MagicMock()

        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock_progess_queue)
        notifier._get_output_filename = mock.MagicMock(
            return_value=fake_output_name)

        gcs_path = '{}/{}'.format('gs://abcd', fake_output_name)

        mock_tmp_csv = mock.MagicMock()
        mock_tempfile.return_value = mock_tmp_csv
        mock_tmp_csv.name = fake_tmpname
        mock_tmp_csv.write = mock.MagicMock()

        # act
        notifier._upload_to_gcs([{}])

        # assert
        mock_tmp_csv.write.assert_called()
        mock_storage.return_value.put_text_file.assert_called_once_with(
            fake_tmpname, gcs_path)
        mock_progess_queue.put.assert_called()

    @mock.patch('google.cloud.forseti.common.util.parser.json_stringify')
    @mock.patch('google.cloud.forseti.common.data_access.csv_writer.write_csv')
    def test_run_with_json(self, mock_write_csv, mock_json_stringify):
        """Test run() with json file format."""
        # arrange
        mock_json_stringify.return_value = 'test123'
        fake_output_name = 'abc'
        mock_service_config = mock.MagicMock()
        mock_service_config.get_notifier_config.return_value = {
            'inventory': {'gcs_summary': {'enabled': True,
                                          'data_format': 'json',
                                          'gcs_path': 'gs://abcd'}}}
        mock_progess_queue = mock.MagicMock()

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock_progess_queue)
        notifier._get_output_filename = mock.MagicMock(
            return_value=fake_output_name)
        notifier._upload_to_gcs([{}])

        # assert
        self.assertTrue(notifier._get_output_filename.called)
        self.assertEqual(
            string_formats.INVENTORY_SUMMARY_JSON_FMT,
            notifier._get_output_filename.call_args[0][0])
        self.assertFalse(mock_write_csv.called)
        self.assertTrue(mock_json_stringify.called)
        mock_progess_queue.put.assert_called()

    @mock.patch('google.cloud.forseti.common.util.parser.json_stringify')
    @mock.patch('google.cloud.forseti.common.data_access.csv_writer.write_csv')
    def test_upload_to_gcs_with_invalid_data_format(self,
                                                    mock_write_csv,
                                                    mock_json_stringify):
        """Test run() with json file format."""
        # arrange
        mock_service_config = mock.MagicMock()
        mock_service_config.get_notifier_config.return_value = {
            'inventory': {'gcs_summary': {'enabled': True,
                                          'data_format': 'blah',
                                          'gcs_path': 'gs://abcd'}}}
        mock_progess_queue = mock.MagicMock()

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock_progess_queue)
        notifier._get_output_filename = mock.MagicMock()

        # assert
        with self.assertRaises(base_notification.InvalidDataFormatError):
            notifier._upload_to_gcs([{}])

        self.assertFalse(notifier._get_output_filename.called)
        self.assertFalse(mock_write_csv.called)
        self.assertFalse(mock_json_stringify.called)
        self.assertFalse(mock_progess_queue.put.called)

    @mock.patch('google.cloud.forseti.notifier.notifiers.inventory_summary.LOGGER', autospec=True)
    def test_gcs_path_is_not_set_in_config(self, mock_logger):
        """Test run() with json file format."""
        # arrange
        mock_service_config = mock.MagicMock()
        mock_service_config.get_notifier_config.return_value = {
            'inventory': {'gcs_summary': {'enabled': True,
                                          'data_format': 'blah'}}}

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock.MagicMock())
        notifier._get_output_filename = mock.MagicMock()
        notifier._upload_to_gcs([{}])

        # assert
        self.assertTrue(mock_logger.error.called)
        self.assertEqual(
            'gcs_path not set for inventory summary notifier.',
            mock_logger.error.call_args[0][0])

    @mock.patch('google.cloud.forseti.notifier.notifiers.inventory_summary.LOGGER', autospec=True)
    def test_inventory_summary_invalid_gcs_path(self, mock_logger):
        # arrange
        mock_service_config = mock.MagicMock()
        mock_service_config.get_notifier_config.return_value = {
            'inventory': {'gcs_summary': {'enabled': True,
                                          'data_format': 'blah',
                                          'gcs_path': 'blah'}}}

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock.MagicMock())
        notifier._get_output_filename = mock.MagicMock()
        notifier._upload_to_gcs([{}])

        # assert
        self.assertTrue(mock_logger.error.called)
        self.assertTrue('Invalid GCS path' in mock_logger.error.call_args[0][0])

    @mock.patch('google.cloud.forseti.notifier.notifiers.inventory_summary.LOGGER', autospec=True)
    def test_no_inventory_in_config(self, mock_logger):
        # arrange
        mock_service_config = mock.MagicMock()
        mock_service_config.get_notifier_config.return_value = dict()

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock.MagicMock())
        notifier.run()

        # assert
        self.assertTrue(mock_logger.info.called)
        self.assertEqual(
            'No inventory configuration for notifier.',
            mock_logger.info.call_args[0][0])

    @mock.patch('google.cloud.forseti.notifier.notifiers.inventory_summary.LOGGER', autospec=True)
    def test_no_inventory_summary_in_config(self, mock_logger):
        # arrange
        mock_service_config = mock.MagicMock()
        mock_service_config.get_notifier_config.return_value = {
            'inventory': {'blah': 'blah blah'}}

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock.MagicMock())
        notifier.run()

        # assert
        self.assertTrue(
            ('unable to get inventory summary configuration'
             in mock_logger.exception.call_args[0][0]))

    @mock.patch('google.cloud.forseti.notifier.notifiers.inventory_summary.LOGGER', autospec=True)
    def test_inventory_summary_not_enabled_in_config(self, mock_logger):
        # arrange
        mock_service_config = mock.MagicMock()
        mock_service_config.get_notifier_config.return_value = {
            'inventory': {'gcs_summary': {'enabled': False},
                          'email_summary': {'enabled': False}}}

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock.MagicMock())
        notifier.run()

        # assert
        self.assertTrue(mock_logger.info.called)
        self.assertEqual(
            'All inventory summaries are disabled.',
            mock_logger.info.call_args[0][0])

    @mock.patch('google.cloud.forseti.notifier.notifiers.inventory_summary.LOGGER', autospec=True)
    def test_inventory_summary_no_summary_data(self, mock_logger):
        # arrange
        mock_service_config = mock.MagicMock()
        mock_service_config.get_notifier_config.return_value = {
            'inventory': {'gcs_summary': {'enabled': True,
                                          'data_format': 'csv',
                                          'gcs_path': 'gs://blah'},
                          'email_summary': {'enabled': True,
                                            'sendgrid_api_key': 'blah',
                                            'sender': 'blah',
                                            'recipient': 'blah'}}}

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock.MagicMock())
        notifier._get_summary_data = mock.MagicMock()
        notifier._get_summary_data.side_effect = util_errors.NoDataError
        notifier.run()

        # assert
        self.assertTrue(mock_logger.exception.called)
        self.assertTrue('no summary data is found'
                        in mock_logger.exception.call_args[0][0])

    def test_get_gsuite_dwd_status_disabled(self):
        # arrange
        mock_inventory_summary_data = [
            {'resource_type': 'bucket', 'count': 2},
            {'resource_type': 'dataset', 'count': 4},
            {'resource_type': 'folder', 'count': 1},
            {'resource_type': 'object', 'count': 1},
            {'resource_type': 'organization', 'count': 1},
            {'resource_type': 'project', 'count': 2}
        ]
        mock_service_config = mock.MagicMock()

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock.MagicMock())
        test_get_gsuite_dwd_status_output = (
            notifier._get_gsuite_dwd_status(
                mock_inventory_summary_data))

        # assert
        self.assertEqual('disabled', test_get_gsuite_dwd_status_output)

    def test_get_gsuite_dwd_status_enabled(self):
        # arrange
        mock_inventory_summary_data = [
            {'resource_type': 'bucket', 'count': 2},
            {'resource_type': 'dataset', 'count': 4},
            {'resource_type': 'folder', 'count': 1},
            {'resource_type': 'gsuite_group', 'count': 4},
            {'resource_type': 'gsuite_user', 'count': 2},
            {'resource_type': 'object', 'count': 1},
            {'resource_type': 'organization', 'count': 1},
            {'resource_type': 'project', 'count': 2}
        ]
        mock_service_config = mock.MagicMock()

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock.MagicMock())
        test_get_gsuite_dwd_status_output = (
            notifier._get_gsuite_dwd_status(
                mock_inventory_summary_data))

        # assert
        self.assertEqual('enabled',
                         test_get_gsuite_dwd_status_output)

    def test_inventory_summary_can_run_successfully(self):
        # arrange
        mock_inventory_index = mock.MagicMock()
        mock_inventory_index.get_summary.return_value = {
            'bucket': 2,
            'dataset': 4,
            'folder': 1,
            'object': 1,
            'organization': 1,
            'project': 2}

        mock_inventory_index.get_details.return_value = {
            'dataset - HIDDEN': 2,
            'dataset - SHOWN': 2,
            'project - ACTIVE': 1,
            'project - DELETE PENDING': 1}

        mock_session = mock.MagicMock()
        mock_session.query.return_value.get.return_value = mock_inventory_index

        mock_service_config = mock.MagicMock()
        mock_service_config.scoped_session.return_value.__enter__.return_value \
            = mock_session
        mock_service_config.get_notifier_config.return_value = {
            'inventory': {'gcs_summary': {'enabled': True,
                                          'data_format': 'csv',
                                          'gcs_path': 'gs://blah'},
                          'email_summary': {'enabled': True,
                                            'sendgrid_api_key': 'blah',
                                            'sender': 'blah',
                                            'recipient': 'blah'}}}

        # act
        notifier = inventory_summary.InventorySummary(mock_service_config,
                                                      'abcd',
                                                      mock.MagicMock())
        mock_get_root_resources = mock.MagicMock()
        mock_get_root_resources.return_value = ['111', '222', '333']
        notifier._get_root_resources = mock_get_root_resources

        notifier._upload_to_gcs = mock.MagicMock()
        notifier._send_email = mock.MagicMock()
        notifier.run()

        # assert
        expected_summary_data_upload_to_gcs = [
            {'count': 2, 'resource_type': 'bucket'},
            {'count': 4, 'resource_type': 'dataset'},
            {'count': 2, 'resource_type': 'dataset - HIDDEN'},
            {'count': 2, 'resource_type': 'dataset - SHOWN'},
            {'count': 1, 'resource_type': 'folder'},
            {'count': 1, 'resource_type': 'object'},
            {'count': 1, 'resource_type': 'organization'},
            {'count': 2, 'resource_type': 'project'},
            {'count': 1, 'resource_type': 'project - ACTIVE'},
            {'count': 1, 'resource_type': 'project - DELETE PENDING'}]

        expected_summary_data_send_email = (
            [
                {'count': 2, 'resource_type': 'bucket'},
                {'count': 4, 'resource_type': 'dataset'},
                {'count': 1, 'resource_type': 'folder'},
                {'count': 1, 'resource_type': 'object'},
                {'count': 1, 'resource_type': 'organization'},
                {'count': 2, 'resource_type': 'project'}],
            [
                {'count': 2, 'resource_type': 'dataset - HIDDEN'},
                {'count': 2, 'resource_type': 'dataset - SHOWN'},
                {'count': 1, 'resource_type': 'project - ACTIVE'},
                {'count': 1, 'resource_type': 'project - DELETE PENDING'}],
            [
                '111',
                '222',
                '333']
        )
        
        self.assertEqual(1, notifier._upload_to_gcs.call_count)
        self.assertEqual(
            expected_summary_data_upload_to_gcs,
            notifier._upload_to_gcs.call_args[0][0])

        self.assertEqual(1, notifier._send_email.call_count)
        self.assertEqual(
            expected_summary_data_send_email,
            notifier._send_email.call_args[0])


if __name__ == '__main__':
    unittest.main()
