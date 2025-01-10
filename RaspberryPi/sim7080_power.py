from gpiozero import OutputDevice
from time import sleep

# GPIO ピン番号 (BCM モード)
powerKey = 4  # GPIO4 (物理ピン7)

# グローバル変数
command_input = ''
rec_buff = ''

# powerOn 関数
def powerOn(powerKey):
    print('SIM7080X is starting...')
    # GPIO 設定
    pwrkey = OutputDevice(powerKey, active_high=True, initial_value=False)

    # PWRKEY をトグル
    pwrkey.on()  # HIGH に設定
    sleep(1)  # 1秒間保持
    pwrkey.off()  # LOW に戻す
    sleep(5)  # SIM7080G の起動を待機
    print('SIM7080X should now be powered on.')

if __name__ == '__main__':
    powerOn(powerKey)
