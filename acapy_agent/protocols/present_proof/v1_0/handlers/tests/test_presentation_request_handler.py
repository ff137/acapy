from unittest import IsolatedAsyncioTestCase

from ......core.oob_processor import OobMessageProcessor
from ......indy.holder import IndyHolder
from ......indy.models.pres_preview import (
    IndyPresAttrSpec,
    IndyPresPredSpec,
    IndyPresPreview,
)
from ......messaging.request_context import RequestContext
from ......messaging.responder import MockResponder
from ......storage.error import StorageNotFoundError
from ......tests import mock
from ......transport.inbound.receipt import MessageReceipt
from ......utils.testing import create_test_profile
from .....didcomm_prefix import DIDCommPrefix
from ...messages.presentation_proposal import PresentationProposal
from ...messages.presentation_request import PresentationRequest
from .. import presentation_request_handler as test_module

S_ID = "NcYxiDXkpYi6ov5FcYDi1e:2:vidya:1.0"
CD_ID = f"NcYxiDXkpYi6ov5FcYDi1e:3:CL:{S_ID}:tag1"
INDY_PROOF_REQ = {
    "name": "proof-req",
    "version": "1.0",
    "nonce": "12345",
    "requested_attributes": {
        "0_player_uuid": {
            "name": "player",
            "restrictions": [{"cred_def_id": CD_ID}],
        },
        "0_screencapture_uuid": {
            "name": "screenCapture",
            "restrictions": [{"cred_def_id": CD_ID}],
        },
    },
    "requested_predicates": {
        "0_highscore_GE_uuid": {
            "name": "highScore",
            "p_type": ">=",
            "p_value": 1000000,
            "restrictions": [{"cred_def_id": CD_ID}],
        }
    },
}
PRES_PREVIEW = IndyPresPreview(
    attributes=[
        IndyPresAttrSpec(name="player", cred_def_id=CD_ID, value="Richie Knucklez"),
        IndyPresAttrSpec(
            name="screenCapture",
            cred_def_id=CD_ID,
            mime_type="image/png",
            value="aW1hZ2luZSBhIHNjcmVlbiBjYXB0dXJl",
        ),
    ],
    predicates=[
        IndyPresPredSpec(
            name="highScore", cred_def_id=CD_ID, predicate=">=", threshold=1000000
        )
    ],
)


class TestPresentationRequestHandler(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.request_context = RequestContext.test_context(await create_test_profile())
        self.mock_oob_processor = mock.MagicMock(OobMessageProcessor, autospec=True)
        self.mock_oob_processor.find_oob_record_for_inbound_message = mock.CoroutineMock(
            return_value=mock.MagicMock()
        )
        self.request_context.injector.bind_instance(
            OobMessageProcessor, self.mock_oob_processor
        )

    async def test_called(self):
        self.request_context.connection_record = mock.MagicMock()
        self.request_context.connection_record.connection_id = "dummy"
        self.request_context.message_receipt = MessageReceipt()
        self.request_context.message = PresentationRequest()
        self.request_context.message.indy_proof_request = mock.MagicMock(
            return_value=INDY_PROOF_REQ
        )

        px_rec_instance = test_module.V10PresentationExchange(
            presentation_proposal_dict={
                "presentation_proposal": {
                    "@type": DIDCommPrefix.qualify_current(
                        "present-proof/1.0/presentation-preview"
                    ),
                    "attributes": [
                        {"name": "favourite", "cred_def_id": CD_ID, "value": "potato"},
                        {"name": "icon", "cred_def_id": CD_ID, "value": "cG90YXRv"},
                    ],
                    "predicates": [],
                }
            },
            auto_present=True,
        )

        with (
            mock.patch.object(
                test_module, "PresentationManager", autospec=True
            ) as mock_pres_mgr,
            mock.patch.object(
                test_module, "V10PresentationExchange", autospec=True
            ) as mock_pres_ex_cls,
        ):
            mock_pres_ex_cls.retrieve_by_tag_filter = mock.CoroutineMock(
                return_value=px_rec_instance
            )

            mock_pres_mgr.return_value.receive_request = mock.CoroutineMock(
                return_value=mock.MagicMock()
            )
            mock_pres_mgr.return_value.receive_request.return_value.auto_present = False

            self.request_context.connection_ready = True
            handler = test_module.PresentationRequestHandler()
            responder = MockResponder()
            await handler.handle(self.request_context, responder)

        mock_pres_mgr.return_value.receive_request.assert_called_once_with(
            px_rec_instance
        )
        self.mock_oob_processor.find_oob_record_for_inbound_message.assert_called_once_with(
            self.request_context
        )
        assert not responder.messages

    async def test_called_not_found(self):
        self.request_context.connection_record = mock.MagicMock()
        self.request_context.connection_record.connection_id = "dummy"
        self.request_context.message_receipt = MessageReceipt()
        self.request_context.message = PresentationRequest()
        self.request_context.message.indy_proof_request = mock.MagicMock(
            return_value=INDY_PROOF_REQ
        )

        px_rec_instance = test_module.V10PresentationExchange(
            presentation_proposal_dict={
                "presentation_proposal": {
                    "@type": DIDCommPrefix.qualify_current(
                        "present-proof/1.0/presentation-preview"
                    ),
                    "attributes": [
                        {"name": "favourite", "cred_def_id": CD_ID, "value": "potato"},
                        {"name": "icon", "cred_def_id": CD_ID, "value": "cG90YXRv"},
                    ],
                    "predicates": [],
                }
            },
            auto_present=True,
        )

        with (
            mock.patch.object(
                test_module, "PresentationManager", autospec=True
            ) as mock_pres_mgr,
            mock.patch.object(
                test_module, "V10PresentationExchange", autospec=True
            ) as mock_pres_ex_cls,
        ):
            mock_pres_ex_cls.retrieve_by_tag_filter = mock.CoroutineMock(
                side_effect=StorageNotFoundError
            )
            mock_pres_ex_cls.return_value = px_rec_instance

            mock_pres_mgr.return_value.receive_request = mock.CoroutineMock(
                return_value=mock.MagicMock()
            )
            mock_pres_mgr.return_value.receive_request.return_value.auto_present = False

            self.request_context.connection_ready = True
            handler = test_module.PresentationRequestHandler()
            responder = MockResponder()
            await handler.handle(self.request_context, responder)

        mock_pres_mgr.return_value.receive_request.assert_called_once_with(
            px_rec_instance
        )
        self.mock_oob_processor.find_oob_record_for_inbound_message.assert_called_once_with(
            self.request_context
        )
        assert not responder.messages

    async def test_called_auto_present(self):
        self.request_context.connection_record = mock.MagicMock()
        self.request_context.connection_record.connection_id = "dummy"
        self.request_context.message = PresentationRequest()
        self.request_context.message.indy_proof_request = mock.MagicMock(
            return_value={
                "name": "proof-request",
                "version": "1.0",
                "nonce": "1234567890",
                "requested_attributes": {
                    "0_favourite_uuid": {
                        "name": "favourite",
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    },
                    "1_icon_uuid": {
                        "name": "icon",
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    },
                },
                "requested_predicates": {},
            }
        )
        self.request_context.message_receipt = MessageReceipt()
        presentation_proposal = PresentationProposal(
            comment="Hello World", presentation_proposal=PRES_PREVIEW
        )
        px_rec_instance = test_module.V10PresentationExchange(
            presentation_proposal_dict=presentation_proposal,
            auto_present=True,
        )

        mock_holder = mock.MagicMock(IndyHolder, autospec=True)
        mock_holder.get_credentials_for_presentation_request_by_referent = (
            mock.CoroutineMock(return_value=[{"cred_info": {"referent": "dummy"}}])
        )
        self.request_context.injector.bind_instance(IndyHolder, mock_holder)

        with (
            mock.patch.object(
                test_module, "PresentationManager", autospec=True
            ) as mock_pres_mgr,
            mock.patch.object(
                test_module, "V10PresentationExchange", autospec=True
            ) as mock_pres_ex_cls,
        ):
            mock_pres_ex_cls.return_value = px_rec_instance
            mock_pres_ex_cls.retrieve_by_tag_filter = mock.CoroutineMock(
                return_value=px_rec_instance
            )
            mock_pres_mgr.return_value.receive_request = mock.CoroutineMock(
                return_value=px_rec_instance
            )

            mock_pres_mgr.return_value.create_presentation = mock.CoroutineMock(
                return_value=(px_rec_instance, "presentation_message")
            )
            self.request_context.connection_ready = True
            handler = test_module.PresentationRequestHandler()
            responder = MockResponder()
            await handler.handle(self.request_context, responder)
            mock_pres_mgr.return_value.create_presentation.assert_called_once()

        mock_pres_mgr.return_value.receive_request.assert_called_once_with(
            px_rec_instance
        )
        self.mock_oob_processor.find_oob_record_for_inbound_message.assert_called_once_with(
            self.request_context
        )
        messages = responder.messages
        assert len(messages) == 1
        (result, target) = messages[0]
        assert result == "presentation_message"
        assert target == {}

    async def test_called_auto_present_x(self):
        self.request_context.connection_record = mock.MagicMock()
        self.request_context.connection_record.connection_id = "dummy"
        self.request_context.message = PresentationRequest()
        self.request_context.message.indy_proof_request = mock.MagicMock(
            return_value={
                "name": "proof-request",
                "version": "1.0",
                "nonce": "1234567890",
                "requested_attributes": {
                    "0_favourite_uuid": {
                        "name": "favourite",
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    },
                    "1_icon_uuid": {
                        "name": "icon",
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    },
                },
                "requested_predicates": {},
            }
        )
        self.request_context.message_receipt = MessageReceipt()
        presentation_proposal = PresentationProposal(
            comment="Hello World", presentation_proposal=PRES_PREVIEW
        )
        mock_px_rec = mock.MagicMock(
            presentation_proposal_dict=presentation_proposal,
            auto_present=True,
            save_error_state=mock.CoroutineMock(),
        )

        mock_holder = mock.MagicMock(IndyHolder, autospec=True)
        mock_holder.get_credentials_for_presentation_request_by_referent = (
            mock.CoroutineMock(return_value=[{"cred_info": {"referent": "dummy"}}])
        )
        self.request_context.injector.bind_instance(IndyHolder, mock_holder)

        with (
            mock.patch.object(
                test_module, "PresentationManager", autospec=True
            ) as mock_pres_mgr,
            mock.patch.object(
                test_module, "V10PresentationExchange", autospec=True
            ) as mock_pres_ex_cls,
        ):
            mock_pres_ex_cls.return_value = mock_px_rec
            mock_pres_ex_cls.retrieve_by_tag_filter = mock.CoroutineMock(
                return_value=mock_px_rec
            )
            mock_pres_mgr.return_value.receive_request = mock.CoroutineMock(
                return_value=mock_px_rec
            )

            mock_pres_mgr.return_value.create_presentation = mock.CoroutineMock(
                side_effect=test_module.IndyHolderError()
            )

            self.request_context.connection_ready = True
            handler = test_module.PresentationRequestHandler()
            responder = MockResponder()

            with mock.patch.object(
                handler._logger, "exception", mock.MagicMock()
            ) as mock_log_exc:
                await handler.handle(self.request_context, responder)
                mock_log_exc.assert_called_once()

    async def test_called_auto_present_no_preview(self):
        self.request_context.connection_record = mock.MagicMock()
        self.request_context.connection_record.connection_id = "dummy"
        self.request_context.message = PresentationRequest()
        self.request_context.message.indy_proof_request = mock.MagicMock(
            return_value={
                "name": "proof-request",
                "version": "1.0",
                "nonce": "1234567890",
                "requested_attributes": {
                    "0_favourite_uuid": {
                        "name": "favourite",
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    },
                    "1_icon_uuid": {
                        "name": "icon",
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    },
                },
                "requested_predicates": {},
            }
        )
        self.request_context.message_receipt = MessageReceipt()
        px_rec_instance = test_module.V10PresentationExchange(auto_present=True)

        mock_holder = mock.MagicMock(IndyHolder, autospec=True)
        mock_holder.get_credentials_for_presentation_request_by_referent = (
            mock.CoroutineMock(return_value=[{"cred_info": {"referent": "dummy"}}])
        )
        self.request_context.injector.bind_instance(IndyHolder, mock_holder)

        with (
            mock.patch.object(
                test_module, "PresentationManager", autospec=True
            ) as mock_pres_mgr,
            mock.patch.object(
                test_module, "V10PresentationExchange", autospec=True
            ) as mock_pres_ex_cls,
        ):
            mock_pres_ex_cls.return_value = px_rec_instance
            mock_pres_ex_cls.retrieve_by_tag_filter = mock.CoroutineMock(
                return_value=px_rec_instance
            )
            mock_pres_mgr.return_value.receive_request = mock.CoroutineMock(
                return_value=px_rec_instance
            )

            mock_pres_mgr.return_value.create_presentation = mock.CoroutineMock(
                return_value=(px_rec_instance, "presentation_message")
            )
            self.request_context.connection_ready = True
            handler = test_module.PresentationRequestHandler()
            responder = MockResponder()
            await handler.handle(self.request_context, responder)
            mock_pres_mgr.return_value.create_presentation.assert_called_once()

        mock_pres_mgr.return_value.receive_request.assert_called_once_with(
            px_rec_instance
        )
        self.mock_oob_processor.find_oob_record_for_inbound_message.assert_called_once_with(
            self.request_context
        )
        messages = responder.messages
        assert len(messages) == 1
        (result, target) = messages[0]
        assert result == "presentation_message"
        assert target == {}

    async def test_called_auto_present_pred_no_match(self):
        self.request_context.connection_record = mock.MagicMock()
        self.request_context.connection_record.connection_id = "dummy"
        self.request_context.message = PresentationRequest()
        self.request_context.message.indy_proof_request = mock.MagicMock(
            return_value={
                "name": "proof-request",
                "version": "1.0",
                "nonce": "1234567890",
                "requested_attributes": {},
                "requested_predicates": {
                    "0_score_GE_uuid": {
                        "name": "score",
                        "p_type": ">=",
                        "p_value": 1000000,
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    }
                },
            }
        )
        self.request_context.message_receipt = MessageReceipt()
        px_rec_instance = test_module.V10PresentationExchange(auto_present=True)

        mock_holder = mock.MagicMock(IndyHolder, autospec=True)
        mock_holder.get_credentials_for_presentation_request_by_referent = (
            mock.CoroutineMock(return_value=[])
        )
        self.request_context.injector.bind_instance(IndyHolder, mock_holder)

        with (
            mock.patch.object(
                test_module, "PresentationManager", autospec=True
            ) as mock_pres_mgr,
            mock.patch.object(
                test_module, "V10PresentationExchange", autospec=True
            ) as mock_pres_ex_cls,
        ):
            mock_pres_ex_cls.return_value = px_rec_instance
            mock_pres_ex_cls.retrieve_by_tag_filter = mock.CoroutineMock(
                return_value=px_rec_instance
            )
            mock_pres_mgr.return_value.receive_request = mock.CoroutineMock(
                return_value=px_rec_instance
            )

            mock_pres_mgr.return_value.create_presentation = mock.CoroutineMock(
                return_value=(px_rec_instance, "presentation_message")
            )
            self.request_context.connection_ready = True
            handler = test_module.PresentationRequestHandler()
            responder = MockResponder()
            await handler.handle(self.request_context, responder)
            mock_pres_mgr.return_value.create_presentation.assert_not_called()

        mock_pres_mgr.return_value.receive_request.assert_called_once_with(
            px_rec_instance
        )
        self.mock_oob_processor.find_oob_record_for_inbound_message.assert_called_once_with(
            self.request_context
        )
        assert not responder.messages

    async def test_called_auto_present_pred_single_match(self):
        self.request_context.connection_record = mock.MagicMock()
        self.request_context.connection_record.connection_id = "dummy"
        self.request_context.message = PresentationRequest()
        self.request_context.message.indy_proof_request = mock.MagicMock(
            return_value={
                "name": "proof-request",
                "version": "1.0",
                "nonce": "1234567890",
                "requested_attributes": {},
                "requested_predicates": {
                    "0_score_GE_uuid": {
                        "name": "score",
                        "p_type": ">=",
                        "p_value": 1000000,
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    }
                },
            }
        )
        self.request_context.message_receipt = MessageReceipt()
        px_rec_instance = test_module.V10PresentationExchange(auto_present=True)

        mock_holder = mock.MagicMock(IndyHolder, autospec=True)
        mock_holder.get_credentials_for_presentation_request_by_referent = (
            mock.CoroutineMock(return_value=[{"cred_info": {"referent": "dummy-0"}}])
        )
        self.request_context.injector.bind_instance(IndyHolder, mock_holder)

        with (
            mock.patch.object(
                test_module, "PresentationManager", autospec=True
            ) as mock_pres_mgr,
            mock.patch.object(
                test_module, "V10PresentationExchange", autospec=True
            ) as mock_pres_ex_cls,
        ):
            mock_pres_ex_cls.return_value = px_rec_instance
            mock_pres_ex_cls.retrieve_by_tag_filter = mock.CoroutineMock(
                return_value=px_rec_instance
            )
            mock_pres_mgr.return_value.receive_request = mock.CoroutineMock(
                return_value=px_rec_instance
            )

            mock_pres_mgr.return_value.create_presentation = mock.CoroutineMock(
                return_value=(px_rec_instance, "presentation_message")
            )
            self.request_context.connection_ready = True
            handler = test_module.PresentationRequestHandler()
            responder = MockResponder()
            await handler.handle(self.request_context, responder)
            mock_pres_mgr.return_value.create_presentation.assert_called_once()

        mock_pres_mgr.return_value.receive_request.assert_called_once_with(
            px_rec_instance
        )
        self.mock_oob_processor.find_oob_record_for_inbound_message.assert_called_once_with(
            self.request_context
        )
        messages = responder.messages
        assert len(messages) == 1
        (result, target) = messages[0]
        assert result == "presentation_message"
        assert target == {}

    async def test_called_auto_present_pred_multi_match(self):
        self.request_context.connection_record = mock.MagicMock()
        self.request_context.connection_record.connection_id = "dummy"
        self.request_context.message = PresentationRequest()
        self.request_context.message.indy_proof_request = mock.MagicMock(
            return_value={
                "name": "proof-request",
                "version": "1.0",
                "nonce": "1234567890",
                "requested_attributes": {},
                "requested_predicates": {
                    "0_score_GE_uuid": {
                        "name": "score",
                        "p_type": ">=",
                        "p_value": 1000000,
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    }
                },
            }
        )
        self.request_context.message_receipt = MessageReceipt()
        px_rec_instance = test_module.V10PresentationExchange(auto_present=True)

        mock_holder = mock.MagicMock(IndyHolder, autospec=True)
        mock_holder.get_credentials_for_presentation_request_by_referent = (
            mock.CoroutineMock(
                return_value=[
                    {"cred_info": {"referent": "dummy-0"}},
                    {"cred_info": {"referent": "dummy-1"}},
                ]
            )
        )
        self.request_context.injector.bind_instance(IndyHolder, mock_holder)

        with (
            mock.patch.object(
                test_module, "PresentationManager", autospec=True
            ) as mock_pres_mgr,
            mock.patch.object(
                test_module, "V10PresentationExchange", autospec=True
            ) as mock_pres_ex_cls,
        ):
            mock_pres_ex_cls.return_value = px_rec_instance
            mock_pres_ex_cls.retrieve_by_tag_filter = mock.CoroutineMock(
                return_value=px_rec_instance
            )
            mock_pres_mgr.return_value.receive_request = mock.CoroutineMock(
                return_value=px_rec_instance
            )

            mock_pres_mgr.return_value.create_presentation = mock.CoroutineMock(
                return_value=(px_rec_instance, "presentation_message")
            )
            self.request_context.connection_ready = True
            handler = test_module.PresentationRequestHandler()
            responder = MockResponder()
            await handler.handle(self.request_context, responder)
            mock_pres_mgr.return_value.create_presentation.assert_called_once()

        mock_pres_mgr.return_value.receive_request.assert_called_once_with(
            px_rec_instance
        )
        self.mock_oob_processor.find_oob_record_for_inbound_message.assert_called_once_with(
            self.request_context
        )
        messages = responder.messages
        assert len(messages) == 1
        (result, target) = messages[0]
        assert result == "presentation_message"
        assert target == {}

    async def test_called_auto_present_multi_cred_match_reft(self):
        self.request_context.connection_record = mock.MagicMock()
        self.request_context.connection_record.connection_id = "dummy"
        self.request_context.message = PresentationRequest()
        self.request_context.message.indy_proof_request = mock.MagicMock(
            return_value={
                "name": "proof-request",
                "version": "1.0",
                "nonce": "1234567890",
                "requested_attributes": {
                    "0_favourite_uuid": {
                        "name": "favourite",
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    },
                    "1_icon_uuid": {
                        "name": "icon",
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    },
                },
                "requested_predicates": {},
            }
        )
        self.request_context.message_receipt = MessageReceipt()
        px_rec_instance = test_module.V10PresentationExchange(
            presentation_proposal_dict={
                "presentation_proposal": {
                    "@type": DIDCommPrefix.qualify_current(
                        "present-proof/1.0/presentation-preview"
                    ),
                    "attributes": [
                        {"name": "favourite", "cred_def_id": CD_ID, "value": "potato"},
                        {"name": "icon", "cred_def_id": CD_ID, "value": "cG90YXRv"},
                    ],
                    "predicates": [],
                }
            },
            auto_present=True,
        )

        mock_holder = mock.MagicMock(IndyHolder, autospec=True)
        mock_holder.get_credentials_for_presentation_request_by_referent = (
            mock.CoroutineMock(
                return_value=[
                    {
                        "cred_info": {
                            "referent": "dummy-0",
                            "cred_def_id": CD_ID,
                            "attrs": {
                                "ident": "zero",
                                "favourite": "potato",
                                "icon": "cG90YXRv",
                            },
                        }
                    },
                    {
                        "cred_info": {
                            "referent": "dummy-1",
                            "cred_def_id": CD_ID,
                            "attrs": {
                                "ident": "one",
                                "favourite": "spud",
                                "icon": "c3B1ZA==",
                            },
                        }
                    },
                    {
                        "cred_info": {
                            "referent": "dummy-2",
                            "cred_def_id": CD_ID,
                            "attrs": {
                                "ident": "two",
                                "favourite": "patate",
                                "icon": "cGF0YXRl",
                            },
                        }
                    },
                ]
            )
        )

        self.request_context.injector.bind_instance(IndyHolder, mock_holder)

        with (
            mock.patch.object(
                test_module, "PresentationManager", autospec=True
            ) as mock_pres_mgr,
            mock.patch.object(
                test_module, "V10PresentationExchange", autospec=True
            ) as mock_pres_ex_cls,
        ):
            mock_pres_ex_cls.return_value = px_rec_instance
            mock_pres_ex_cls.retrieve_by_tag_filter = mock.CoroutineMock(
                return_value=px_rec_instance
            )
            mock_pres_mgr.return_value.receive_request = mock.CoroutineMock(
                return_value=px_rec_instance
            )

            mock_pres_mgr.return_value.create_presentation = mock.CoroutineMock(
                return_value=(px_rec_instance, "presentation_message")
            )
            self.request_context.connection_ready = True
            handler = test_module.PresentationRequestHandler()
            responder = MockResponder()
            await handler.handle(self.request_context, responder)
            mock_pres_mgr.return_value.create_presentation.assert_called_once()

        mock_pres_mgr.return_value.receive_request.assert_called_once_with(
            px_rec_instance
        )
        self.mock_oob_processor.find_oob_record_for_inbound_message.assert_called_once_with(
            self.request_context
        )
        messages = responder.messages
        assert len(messages) == 1
        (result, target) = messages[0]
        assert result == "presentation_message"
        assert target == {}

    async def test_called_auto_present_bait_and_switch(self):
        self.request_context.connection_record = mock.MagicMock()
        self.request_context.connection_record.connection_id = "dummy"
        self.request_context.message = PresentationRequest()
        self.request_context.message.indy_proof_request = mock.MagicMock(
            return_value={
                "name": "proof-request",
                "version": "1.0",
                "nonce": "1234567890",
                "requested_attributes": {
                    "0_favourite_uuid": {
                        "name": "favourite",
                        "restrictions": [
                            {
                                "cred_def_id": CD_ID,
                            }
                        ],
                    }
                },
                "requested_predicates": {},
            }
        )
        self.request_context.message_receipt = MessageReceipt()
        px_rec_instance = test_module.V10PresentationExchange(
            presentation_proposal_dict={
                "presentation_proposal": {
                    "@type": DIDCommPrefix.qualify_current(
                        "present-proof/1.0/presentation-preview"
                    ),
                    "attributes": [
                        {"name": "favourite", "cred_def_id": CD_ID, "value": "potato"}
                    ],
                    "predicates": [],
                }
            },
            auto_present=True,
        )

        by_reft = mock.CoroutineMock(
            return_value=[
                {
                    "cred_info": {
                        "referent": "dummy-0",
                        "cred_def_id": CD_ID,
                        "attrs": {"ident": "zero", "favourite": "yam"},
                    }
                },
                {
                    "cred_info": {
                        "referent": "dummy-1",
                        "cred_def_id": CD_ID,
                        "attrs": {"ident": "one", "favourite": "turnip"},
                    }
                },
                {
                    "cred_info": {
                        "referent": "dummy-2",
                        "cred_def_id": CD_ID,
                        "attrs": {
                            "ident": "two",
                            "favourite": "the idea of a potato but not a potato",
                        },
                    }
                },
            ]
        )
        mock_holder = mock.MagicMock(IndyHolder, autospec=True)
        mock_holder.get_credentials_for_presentation_request_by_referent = by_reft
        self.request_context.injector.bind_instance(IndyHolder, mock_holder)

        with (
            mock.patch.object(
                test_module, "PresentationManager", autospec=True
            ) as mock_pres_mgr,
            mock.patch.object(
                test_module, "V10PresentationExchange", autospec=True
            ) as mock_pres_ex_cls,
        ):
            mock_pres_ex_cls.return_value = px_rec_instance
            mock_pres_ex_cls.retrieve_by_tag_filter = mock.CoroutineMock(
                return_value=px_rec_instance
            )
            mock_pres_mgr.return_value.receive_request = mock.CoroutineMock(
                return_value=px_rec_instance
            )

            mock_pres_mgr.return_value.create_presentation = mock.CoroutineMock(
                return_value=(px_rec_instance, "presentation_message")
            )
            self.request_context.connection_ready = True
            handler = test_module.PresentationRequestHandler()
            responder = MockResponder()

            await handler.handle(self.request_context, responder)
            mock_pres_mgr.return_value.create_presentation.assert_not_called()

        mock_pres_mgr.return_value.receive_request.assert_called_once_with(
            px_rec_instance
        )
        self.mock_oob_processor.find_oob_record_for_inbound_message.assert_called_once_with(
            self.request_context
        )
        assert not responder.messages

    async def test_called_not_ready(self):
        self.request_context.message_receipt = MessageReceipt()
        self.request_context.connection_record = mock.MagicMock()

        with mock.patch.object(
            test_module, "PresentationManager", autospec=True
        ) as mock_pres_mgr:
            mock_pres_mgr.return_value.receive_request = mock.CoroutineMock()
            self.request_context.message = PresentationRequest()
            self.request_context.connection_ready = False
            handler = test_module.PresentationRequestHandler()
            responder = MockResponder()
            with self.assertRaises(test_module.HandlerException) as err:
                await handler.handle(self.request_context, responder)
            assert (
                err.exception.message
                == "Connection used for presentation request not ready"
            )

        assert not responder.messages

    async def test_no_conn_no_oob(self):
        self.request_context.message_receipt = MessageReceipt()
        self.mock_oob_processor = mock.MagicMock(OobMessageProcessor, autospec=True)
        self.mock_oob_processor.find_oob_record_for_inbound_message = mock.CoroutineMock(
            return_value=None
        )
        self.request_context.injector.bind_instance(
            OobMessageProcessor, self.mock_oob_processor
        )
        self.request_context.message = PresentationRequest()
        handler = test_module.PresentationRequestHandler()
        responder = MockResponder()
        with self.assertRaises(test_module.HandlerException) as err:
            await handler.handle(self.request_context, responder)
        assert (
            err.exception.message
            == "No connection or associated connectionless exchange found for presentation request"
        )

        assert not responder.messages
