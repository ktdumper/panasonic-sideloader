import os
import sys
import shutil
import struct
import configparser
from io import StringIO
import re


def rm_f(path):
    try:
        os.remove(path)
    except OSError:
        pass

def patch_jam(jam, jar_len, package_url):
    config = configparser.ConfigParser()
    config.optionxform = str

    try:
        config.read_string("[jam]\r\n" + jam.decode("cp932"))
    except UnicodeDecodeError as e:
        print("WARN: can't patch jam properly due to non-cp932 encoding or other UnicodeDecodeError.")
        print(f"({e})")
        try:
            config.read_string("[jam]\r\n" + jam.decode("cp932", errors="ignore"))
        except configparser.ParsingError:
            return jam

    config["jam"]["PackageURL"] = package_url
    config["jam"]["LastModified"] = "Fri, 01 Jan 2010 00:00:00"
    config["jam"]["AppSize"] = str(jar_len)

    # The document says it needs to be 16 bytes or less, but the reality is different.
    if config["jam"].get("AppName") == None:
        config["jam"]["AppName"] = "No Name"

    if config["jam"].get("AppClass") == None:
        print("WARN: no AppClass in the jam")

    config["jam"]["AccessUserInfo"] = "yes"
    config["jam"]["GetSysInfo"] = "yes"
    config["jam"]["UseTelephone"] = "call"
    config["jam"]["UseDTV"] = "launch"
    config["jam"]["UseStorage"] = "ext"
    config["jam"]["TrustedAPID"] = "00000000000"
    config["jam"]["GetUtn"] = "userid,terminalid"
    config["jam"]["AppTrace"] = "on"
    config["jam"]["LaunchApp"] = "yes"

    # Maximum size of the application.
    if config["jam"].get("SPsize") in [None, ""]:
        sp_size = 0
    else:
        sp_size = sum([int(s) for s in config["jam"].get("SPsize").split(",")])

    if (jar_len + sp_size > 10240000):
        print("WARN: the total size of the jar and sp exceeds 10,240 KB.")

    # for Star
    if config["jam"].get("AppType") in ["FullApp", "MiniApp", "FullApp,MiniApp", "MiniApp,FullApp"]:
        config["jam"]["UseNetwork"] = "yes"
    # for Doja 
    elif config["jam"].get("AppType") == None:
        config["jam"]["UseNetwork"] = "http"
        config["jam"]["MyConcierge"] = "yes"
    else:
        print("WARN: invalid AppType")

    config.remove_option("jam", "TargetDevice")
    config.remove_option("jam", "MessageCode")
    config.remove_option("jam", "ProfileVer")
    config.remove_option("jam", "ConfigurationVer")
    config.remove_option("jam", "KvmVer")

    config_string = StringIO()
    config.write(config_string)

    return config_string.getvalue()[6:].replace("\r\n", "\n").replace("\n", "\r\n").replace("\r\n\r\n", "\r\n").encode("cp932")

def make_sdf(package_url):
    config = configparser.ConfigParser()
    config.optionxform = str
    config["sdf"] = {
        "PackageURL": package_url,
        "CheckCnt": "000",
        "CheckInt": "000",
        "SuspendedCnt": "000",
        "Lmd": "20010606115743",
        "SkipConfirm": "launch",
        "GetLocationInfo": "yes",
        "AllowedHost": "any",
        "UseOpenGL": "yes",
        "UseBluetooth": "yes",
        "UseMailer": "yes",
        "GetPrivateInfo": "yes",
        "UseTcpPeerConnection": "yes",
        "UseUdpPeerConnection ": "yes",
        "UseATF": "yes",
        "UseVoiceInput": "yes",
        "UseDynamicClassLoader": "yes",
        "UseFeliCaOnline": "yes",
        "UseFeliCaOffline": "yes",
        "SetPhoneTheme": "yes",
        "SetLaunchTime": "yes",
        "RequestMyMenu": "yes",
        "RequestPayPerView": "yes",
        "AllowedLauncherApp": "any",
        "AllowedTcpHost": "any:15000",
        "AllowedUdpHost": "any:15000",
        "LaunchBySMS": "yes",
        "LaunchByDTV": "yes",
        "AppID": "000000000",
        
        # Once enabled, it will be removed from the list.
        # "MessageApp": "yes",
        
        "Sts": "0"
    }

    config_string = StringIO()
    config.write(config_string)
    
    sdf = config_string.getvalue()[6:].replace("\r\n", "\n").replace("\n", "\r\n").replace("\r\n\r\n", "\r\n").encode("cp932")
    sdfsize = len(sdf)
    
    sdf_template = struct.pack("<I 4s Q I I",
        0, b"\xB7\xA1\x06\x67", 0, sdfsize, 0)

    return bytearray(sdf_template + sdf)

def main():
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]

    jar_path = sp_path = jam_path = sdf_path = None

    for fname in os.listdir(input_dir):
        if fname.lower().endswith(".jar"):
            jar_path = fname
        elif fname.lower().endswith(".sp"):
            sp_path = fname
        elif fname.lower().endswith(".jam"):
            jam_path = fname
        elif fname.lower().endswith(".sdf"):
            sdf_path = fname

    if jar_path is None:
        raise RuntimeError(f"can't find jar: {input_dir}")
    elif jam_path is None:
        raise RuntimeError(f"can't find jam: {input_dir}")

    if sp_path is not None:
        with open(os.path.join(input_dir, sp_path), "rb") as inf:
            sp = inf.read()

    with open(os.path.join(input_dir, jam_path), "rb") as inf:
        jam = inf.read()

    if package_url := re.search(r"PackageURL\s*=\s*([^\r\n]+)", jam.decode(encoding="cp932", errors="ignore")):
        package_url = package_url[1]
    else:
        package_url = "http://example.com/sample.jar"
        print("WARN: no PackageURL in the jam")

    
    if package_url.startswith("http"):
        jam_download_url = package_url.replace(".jar", ".jam").encode("cp932")
        jar_download_url = package_url.encode("cp932")
    elif m := re.search(r'.+?([^\r\n\/:*?"><|=]+\.jar)', package_url):
        jam_download_url = f'http://example.com/{m[1].replace(".jar", ".jam")}'.encode("cp932")
        jar_download_url = f'http://example.com/{m[1]}'.encode("cp932")
    else:
        jam_download_url = b"http://example.com/sample.jam"
        jar_download_url = b"http://example.com/sample.jar"

    adf_template = struct.pack("<I 2052s 4120s 148s 21496s 265s 2315s",
        1, jam_download_url, jar_download_url, b"\x71\x01", b"\x01", b"\xFF\xFF\xFF\xFF", b"\x01")
    jam = patch_jam(jam, os.path.getsize(os.path.join(input_dir, jar_path)), package_url)

    adf = bytearray(adf_template + jam)
    adf[0x1820:0x1824] = struct.pack("<I", len(jam))
    
    sdf = make_sdf(package_url)

    target = None

    # For P-01F. Verified.
    max_appli = 100

    for x in range(max_appli):
        if not os.path.exists(os.path.join(output_dir, str(x))):
            target = x
            break

    if target is None:
        raise RuntimeError(f"The maximum number of i-applis has been reached: {max_appli}")

    output_path = os.path.join(output_dir, str(target))
    os.mkdir(output_path)

    with open(os.path.join(output_path, "adf"), "wb") as outf:
        outf.write(adf)

    if sp_path is not None:
        with open(os.path.join(output_path, "sp"), "wb") as outf:
            outf.write(sp[0x40:])

    shutil.copyfile(os.path.join(input_dir, jar_path), os.path.join(output_path, "jar"))

    if sdf_path is None:
        with open(os.path.join(output_path, "sdf"), "wb") as outf:
            outf.write(sdf)
    else:
        shutil.copyfile(os.path.join(input_dir, sdf_path), os.path.join(output_path, "sdf"))

    for filename in ["Entry", "JavaAdl", "JavaSys", "PushSms"]:
        rm_f(os.path.join(output_dir, filename))

    print("{} => {}".format(input_dir, output_path))


if __name__ == "__main__":
    main()
