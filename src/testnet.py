import time
from decimal import Decimal

import eth_abi.packed
from web3 import Web3
from loguru import logger

from .utils import search_setting_data, transaction_verification
from .settings import SETTING_TESTNETBRIDGE_LIST


def testnet_bridge(name, private_key, from_chain, max_bridge, max_gas, max_value):
    log_name = f'TESTNET BRIDGE {from_chain} to GOERLIETH'
    to_chain = 'GOERLIETH'

    from_data = search_setting_data(chain=from_chain, list=SETTING_TESTNETBRIDGE_LIST)
    if len(from_data) == 0:
        logger.error(f'{name} | {log_name} | Error while finding information about from_chain')
        return
    else:
        from_data = from_data[0]

    to_data = search_setting_data(chain=to_chain, list=SETTING_TESTNETBRIDGE_LIST)
    if len(to_data) == 0:
        logger.error(f'{name} | {log_name} | Error while finding information about to_chain')
        return
    else:
        to_data = to_data[0]

    ROUND = 6
    RPC_FROM = from_data['RPC']
    RPC_TO = to_data['RPC']
    BRIDGE = from_data['BRIDGE']
    BRIDGE_ABI = from_data['BRIDGE_ABI']
    OFT = from_data['OFT']
    OFT_ABI = from_data['OFT_ABI']
    SLIPPAGE = from_data['SLIPPAGE']
    DSTCHAINID = to_data['CHAINID']

    # Connect and check
    w3_from = Web3(Web3.HTTPProvider(RPC_FROM, request_kwargs={"timeout":120}))
    if w3_from.is_connected() == True:
        account = w3_from.eth.account.from_key(private_key)
        address = account.address
        logger.success(f'{name} | {address} | {log_name} | Connected to {from_chain}')
    else:
        logger.error(f'{name} | {log_name} | Failed connection to {from_chain}')
        return

    w3_to = Web3(Web3.HTTPProvider(RPC_TO, request_kwargs={"timeout":120}))
    if w3_to.is_connected() == True:
        logger.success(f'{name} | {address} | {log_name} | Connected to {to_chain}')
    else:
        logger.error(f'{name} | {log_name} | Failed connection to {to_chain}')
        return

    # Check from
    balance = w3_from.eth.get_balance(address)
    human_balance = round(w3_from.from_wei(balance, "ether").real,ROUND)
    logger.info(f'{name} | {address} | {log_name} | ETH = {human_balance}, {from_chain}')

    # Check for tokens
    if human_balance == 0:
        logger.error(f'{name} | {address} | {log_name} | No tokens') 
        return
    if human_balance > max_bridge:
        amountIn = w3_from.to_wei(max_bridge, "ether")
        amount = round(Decimal(max_bridge), ROUND)
    else:
        amountIn = balance
        amount = human_balance
    logger.info(f'{name} | {address} | {log_name} | BRIDGE {amount} from {from_chain} to {to_chain}')
    amountOutMin = amountIn - (amountIn * SLIPPAGE) // 1000
    human_amountOutMin = round(w3_from.from_wei(amountOutMin, "ether").real, ROUND)
    logger.info(f'{name} | {address} | {log_name} | Min receive {human_amountOutMin} from {from_chain} to {to_chain}')

    # Check to
    balance_to = w3_to.eth.get_balance(address)
    human_balance_to = round(w3_to.from_wei(balance_to, "ether").real, ROUND)
    logger.info(f'{name} | {address} | {log_name} | ETH = {human_balance_to}, {to_chain}')

    # BRIDGE 
    try:
        # ENDPOINT and BRIDGE
        contractENDPOINT = w3_from.eth.contract(address=w3_from.to_checksum_address(OFT), abi=OFT_ABI)
        contractBRIDGE = w3_from.eth.contract(address=w3_from.to_checksum_address(BRIDGE), abi=BRIDGE_ABI)
        nonce = w3_from.eth.get_transaction_count(address)
        while True:
            value = contractENDPOINT.functions.estimateSendFee(
                int(DSTCHAINID),
                w3_from.to_checksum_address(address),
                amountIn,
                False,
                eth_abi.packed.encode_packed([], []),
                ).call()
            value = value[0]
            human_value = round(w3_from.from_wei(value, "ether").real, ROUND)
            if human_value < max_value:
                logger.info(f'{name} | {address} | {log_name} | Value cost on BRIDGE {human_value}, {from_chain}')
            else:
                logger.warning(f'{name} | {address} | {log_name} | Value cost on BRIDGE {human_value}, {from_chain}, > max_value')
                time.sleep(30)
                continue
            
            value_transaction = value + amountIn

            # Check GAS
            gas = contractBRIDGE.functions.swapAndBridge(
                amountIn,
                amountOutMin,
                int(DSTCHAINID),
                address,
                address,
                '0x0000000000000000000000000000000000000000',
                '0x'
                ).estimate_gas({'from': address, 'value':value_transaction , 'nonce': nonce })
            gas = gas * 1.2
            gas_price = w3_from.eth.gas_price
            txCost = gas * gas_price
            txCostInEther = round(w3_from.from_wei(txCost, "ether").real,ROUND)
            if txCostInEther < max_gas:
                logger.info(f'{name} | {address} | {log_name} | Gas cost on BRIDGE {txCostInEther}, {from_chain}')
                break
            else:
                logger.warning(f'{name} | {address} | {log_name} | Gas cost on BRIDGE {txCostInEther}, {from_chain}, > max_gas')
                time.sleep(30)
                continue

        # BRIDGE
        transaction = contractBRIDGE.functions.swapAndBridge(
                    amountIn,
                    amountOutMin,
                    int(DSTCHAINID),
                    address,
                    address,
                    '0x0000000000000000000000000000000000000000',
                    eth_abi.packed.encode_packed(   [],
                                                    [])
            ).build_transaction({
            'from': address,
            'value': value_transaction,
            'gas': int(gas),
            'gasPrice': int(gas_price),
            'nonce': nonce})

        signed_transaction = account.sign_transaction(transaction)
        transaction_hash = w3_from.eth.send_raw_transaction(signed_transaction.rawTransaction)
        logger.success(f'{name} | {address} | {log_name} | Sign BRIDGE: {transaction_hash.hex()}')
        status = transaction_verification(name, transaction_hash, w3_from, from_chain, log_name=log_name, text=f'BRIDGE {from_chain} to {to_chain} amount {amount}', logger=logger)

        if status == False:
            logger.error(f'{name} | {address} | {log_name} | Error BRIDGE {from_chain} to {to_chain} amount {amount}')
            return

    except Exception as Ex:
        if "insufficient funds for gas * price + value" in str(Ex):
            logger.error(f'{name} | {address} | {log_name} | Insufficient funds for BRIDGE {from_chain} to {to_chain}, amount {amount}')
            return
        logger.error(f'{name} | {address} | {log_name} | Error BRIDGE {from_chain} to {to_chain}, amount {amount}')
        return
    
    # Check balance on receiver
    try:
        lv_count = 0
        while lv_count <= 360:
            try:
                balance_to2 = w3_to.eth.get_balance(address)
            except Exception as Ex:
                logger.error(f'{name} | {address} | {log_name} | Error balanceOf, {Ex}')
                time.sleep(60)
                continue
            human_balance_to2 = round(w3_to.from_wei(balance_to2, "ether").real, ROUND)
            logger.info(f'{name} | {address} | {log_name} | ETH = {human_balance_to2}, {to_chain}') 
            if balance_to < balance_to2:
                logger.success(f'{name} | {address} | {log_name} | ETH = {human_balance_to2}, BRIDGE is done') 
                return True
            lv_count += 1
            time.sleep(60)
        logger.error(f'{name} | {address} | {log_name} | ETH = {balance_to2}, not receive BRIDGE') 
        return False
    except Exception as Ex:
        logger.error(f'{name} | {address} | {log_name} | Error while checking BRIDGE amount {amount}')
        return False
