#!/usr/bin/env python3
"""Exercise production HE parsing, negotiation and firmware encoding under ASan/UBSan."""
from pathlib import Path
import re
import subprocess
import tempfile
import struct

root = Path(__file__).resolve().parents[1]
netdir = root / 'itl80211/openbsd/net80211'
net = (netdir / 'ieee80211.h').read_text()
var = (netdir / 'ieee80211_var.h').read_text()
nodeh = (netdir / 'ieee80211_node.h').read_text()
iwx = (root / 'itlwm/hal_iwx/ItlIwx.cpp').read_text()
reg = (root / 'itlwm/hal_iwx/if_iwxreg.h').read_text()

def function(source, name):
    match = re.search(r'^[A-Za-z_][\w *:]*\s+' + re.escape(name) + r'\([^;]*?\n\{.*?\n\}', source, re.M | re.S)
    if not match:
        raise ValueError(name)
    return match.group(0)

def declaration(source, kind, name):
    return re.search(r'\b' + kind + ' ' + name + r'\s*\{.*?\}[^;]*;', source, re.S).group(0)

def defines(source, prefix):
    source = source.replace(chr(92) + chr(10), ' ')
    return '\n'.join(re.findall(r'^#define\s+(?:' + prefix + r')\w*[^\n]*', source, re.M))

parts = [r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <algorithm>
#include <vector>
#define __packed __attribute__((packed))
#define BIT(n) (1U << (n))
#define htole16(x) (x)
#define le16toh(x) (x)
#define le32toh(x) (x)
#define htole32(x) (x)
#define hweight8(x) __builtin_popcount((unsigned)(x))
#define DIV_ROUND_UP(n,d) (((n)+(d)-1)/(d))
#define XYLog(...) ((void)0)
#define min(a,b) std::min(a,b)
''', defines(net, 'IEEE80211_HE_|IEEE80211_PPE_|IEEE80211_CIPHER_'),
    defines(var, 'IEEE80211_F_'), defines(nodeh, 'IEEE80211_NODE_'),
    defines(reg, 'IWX_RATE_|IWX_HE_|IWX_TLC_|IWX_ANT_|IWX_STATION_ID|IWX_DATA_PATH_GROUP|IWX_STA_HE_CTXT_CMD'),
    '#define IWX_FW_CMD_VER_UNKNOWN 99\n#define IEEE80211_HTCAP_CBW20_40 2',
    declaration(net, 'enum', 'ieee80211_he_mcs_support'),
    declaration(var, 'enum', 'ieee80211_phymode'),
    declaration(reg, 'enum', 'iwx_tlc_mng_ht_rates'),
    defines((root/'itlwm/hal_iwx/if_iwxvar.h').read_text(), 'IWX_STATION_ID'),
    defines((netdir/'ieee80211_ioctl.h').read_text(), 'IEEE80211_F_NOVHT')]
for name in ['ieee80211_he_cap_elem', 'ieee80211_he_mcs_nss_supp', 'ieee80211_he_operation', 'ieee80211_he_6ghz_oper']:
    parts.append(declaration(net, 'struct', name))
for name in ['iwx_he_backoff_conf', 'iwx_he_sta_context_cmd']:
    parts.append(declaration(reg, 'struct', name))
parts.append('enum { ' + ','.join(re.findall(r'IEEE80211_CIPHER_(?:USEGROUP|TKIP)\s*=\s*0x[0-9a-fA-F]+', (netdir/'ieee80211_crypto.h').read_text())) + ' };')
parts.append(r'''
enum { IEEE80211_CHAN_WIDTH_20, IEEE80211_CHAN_WIDTH_40, IEEE80211_CHAN_WIDTH_80,
       IEEE80211_CHAN_WIDTH_160, IEEE80211_CHAN_WIDTH_80P80 };
struct ieee80211_channel { unsigned ic_flags, ic_freq, ic_center_freq1, ic_center_freq2; };
#define IEEE80211_IS_CHAN_2GHZ(c) ((c)->ic_flags == 2)
struct ieee80211_node {
    ieee80211_he_cap_elem ni_he_cap_elem;
    ieee80211_he_mcs_nss_supp ni_he_mcs_nss_supp;
    uint8_t ni_ppe_thres[IEEE80211_HE_PPE_THRES_MAX_LEN];
    uint32_t ni_flags, ni_he_oper_params, ni_rsnciphers, ni_he_txrate_kbps;
    uint16_t ni_he_oper_nss_set;
    uint8_t ni_he_optional[9], ni_he_mu_edca[13], ni_he_tx_nss, ni_he_requested, ni_chw, ni_rx_nss;
    ieee80211_channel *ni_chan;
};
struct ieee80211com {
    uint32_t ic_flags, ic_userflags, ic_modecaps, ic_htcaps;
    ieee80211_he_cap_elem ic_he_cap_elem;
    ieee80211_he_mcs_nss_supp ic_he_mcs_nss_supp;
    uint8_t ic_ppe_thres[IEEE80211_HE_PPE_THRES_MAX_LEN];
    ieee80211_node *ic_bss;
    unsigned ic_state;
    void (*ic_updateprot)(ieee80211com *);
};
struct iwx_softc {
    ieee80211com sc_ic;
    struct { bool sku_cap_11ax_enable, sku_cap_band_52GHz_enable, vht160_supported; } sc_nvm;
    uint8_t rx_ant, tx_ant, cmdver;
    bool mimo;
};
struct iwx_tlc_config_cmd_v4 { uint16_t ht_rates[2][2]; };
enum ieee80211_edca_ac { BE, BK, VI, VO };
''')
# Use the actual EDCA mapping constants/function.
parts += [defines(reg, 'IWX_AC_'), function(iwx, 'iwx_mvm_mac80211_ac_to_ucode_ac')]
parts.append(r'''
struct ItlIwx {
    void iwx_setup_he_rates(iwx_softc *);
    uint8_t iwx_lookup_cmd_ver(iwx_softc *s, int, int) { return s->cmdver; }
    uint8_t iwx_fw_valid_rx_ant(iwx_softc *s) { return s->rx_ant; }
    uint8_t iwx_fw_valid_tx_ant(iwx_softc *s) { return s->tx_ant; }
    bool iwx_mimo_enabled(iwx_softc *s) { return s->mimo; }
};
''')
for name in ['ieee80211_he_mcs_intersection','ieee80211_he_mcs_nss_size','ieee80211_he_ppe_size','ieee80211_he_oper_size']:
    parts.append(function(net,name))
for filename,names in {
    'ieee80211_node.c':['ieee80211_setup_hecaps','ieee80211_setup_heop'],
    'ieee80211_output.c':['ieee80211_add_hecaps'],
    'ieee80211_input.c':['ieee80211_update_he_params'],
    'ieee80211_proto.c':['ieee80211_he_supported','ieee80211_he_negotiate'],
}.items():
    for name in names: parts.append(function((netdir/filename).read_text(),name))
parts.insert(0, '#define IEEE80211_S_RUN 4\n#define IEEE80211_ELEMID_EXTENSION 255\n#define IEEE80211_ELEMID_EXT_HE_CAPABILITY 35\n')
for name in ['iwx_num_of_ant','iwx_setup_he_rates','rs_fw_he_ieee80211_mcs_to_rs_mcs','iwx_rs_fw_he_set_enabled_rates','iwx_he_ppe_value','iwx_build_he_sta','iwx_he_rate_kbps']:
    parts.append(function(iwx,name))
parts.append(r'''
static iwx_softc enabled() {
    iwx_softc s = {};
    s.rx_ant = s.tx_ant = 3; s.mimo = true; s.cmdver = 2;
    s.sc_nvm = {true, true, true};
    s.sc_ic.ic_flags = IEEE80211_F_HTON | IEEE80211_F_VHTON;
    s.sc_ic.ic_userflags = IEEE80211_F_HEON;
    s.sc_ic.ic_htcaps = IEEE80211_HTCAP_CBW20_40;
    ItlIwx().iwx_setup_he_rates(&s);
    s.sc_ic.ic_modecaps = 1 << IEEE80211_MODE_11AX;
    return s;
}
int main() {
    static_assert(sizeof(iwx_he_sta_context_cmd) == 88, "wire ABI");
    static_assert(offsetof(iwx_he_sta_context_cmd, bss_color) == 40, "wire ABI");
    static_assert(offsetof(iwx_he_sta_context_cmd, max_bssid_indicator) == 80, "v1 length");
    auto s = enabled(); auto &ic = s.sc_ic;
    assert(ic.ic_flags & IEEE80211_F_HEON);
    assert(ic.ic_he_mcs_nss_supp.rx_mcs_80 == 0xfffa);
    for (unsigned scenario=0; scenario<5; scenario++) {
        auto no = enabled();
        if (scenario==0) no.sc_ic.ic_userflags = 0;
        if (scenario==1) no.sc_nvm.sku_cap_11ax_enable = false;
        if (scenario==2) no.sc_ic.ic_userflags |= IEEE80211_F_NOVHT;
        if (scenario==3) no.cmdver = 3;
        if (scenario==4) no.rx_ant = 0;
        ItlIwx().iwx_setup_he_rates(&no);
        assert(!(no.sc_ic.ic_flags & IEEE80211_F_HEON));
    }
    auto single = enabled(); single.tx_ant=1;
    ItlIwx().iwx_setup_he_rates(&single);
    assert(single.sc_ic.ic_he_mcs_nss_supp.tx_mcs_80 == 0xfffe);
    assert(single.sc_ic.ic_he_mcs_nss_supp.rx_mcs_80 == 0xfffa);
    single.mimo=false; ItlIwx().iwx_setup_he_rates(&single);
    assert(single.sc_ic.ic_he_mcs_nss_supp.rx_mcs_80 == 0xfffe);
    // Every truncation of a valid variable-length IE must fail, without reading past it.
    uint8_t wire[128] = {}; ieee80211_node ni = {};
    for (unsigned widths=0; widths<4; widths++) for (unsigned ppe=0; ppe<2; ppe++) {
        auto c = ic;
        c.ic_he_cap_elem.phy_cap_info[0] = ((widths&1)?8:0) | ((widths&2)?16:0);
        c.ic_he_mcs_nss_supp.rx_mcs_80p80=0xfffd;
        c.ic_he_cap_elem.phy_cap_info[6] = ppe ? IEEE80211_HE_PHY_CAP6_PPE_THRESHOLD_PRESENT : 0;
        c.ic_ppe_thres[0] = 0x79; // 2 streams, all four RU sizes
        auto end = ieee80211_add_hecaps(wire,&c);
        assert(wire[1] == end-wire-2);
        unsigned length=end-wire-3;
        for (unsigned n=0;n<length;n++) {
            std::vector<uint8_t> cut(wire+3,wire+3+n);
            assert(!ieee80211_setup_hecaps(&ni,cut.data(),n));
            assert(!(ni.ni_flags & IEEE80211_NODE_HECAP));
        }
        assert(ieee80211_setup_hecaps(&ni,wire+3,length));
        assert(ni.ni_he_mcs_nss_supp.rx_mcs_160 == ((widths&1)?0xfffa:0xffff));
        assert(ni.ni_he_mcs_nss_supp.rx_mcs_80p80 == ((widths&2)?0xfffd:0xffff));
    }
    for (unsigned option=0;option<8;option++) {
        uint8_t op[15]={}; uint32_t params=0;
        if(option&1) params|=IEEE80211_HE_OPERATION_VHT_OPER_INFO;
        if(option&2) params|=IEEE80211_HE_OPERATION_CO_HOSTED_BSS;
        if(option&4) params|=IEEE80211_HE_OPERATION_6GHZ_OP_INFO;
        memcpy(op,&params,4);op[4]=0xfc;op[5]=0xff;
        unsigned length=ieee80211_he_oper_size(op)-1;
        for(unsigned n=0;n<length;n++) {
            std::vector<uint8_t> cut(op,op+n);
            assert(!ieee80211_setup_heop(&ni,cut.data(),n));
        }
        assert(ieee80211_setup_heop(&ni,op,length));
    }
    // Random exact-size buffers exercise PPE/header parsing with sanitizers.
    uint32_t random=123;
    for(unsigned n=0;n<256;n++) for(unsigned j=0;j<32;j++) {
        std::vector<uint8_t> bytes(n);
        for(auto &v:bytes) { random=random*1664525+1013904223;v=random>>24; }
        ieee80211_setup_hecaps(&ni,bytes.data(),n);
        ieee80211_setup_heop(&ni,bytes.data(),n);
    }
    // Intersections are directional, and unsupported is not a lower MCS.
    for(unsigned a=0;a<4;a++) for(unsigned b=0;b<4;b++) {
        unsigned x=ieee80211_he_mcs_intersection(0xfffc|a,0xfffc|b)&3;
        if(a==3 || b==3) assert(x==3); else assert(x<=a && x<=b && (x==a || x==b));
    }
    auto end = ieee80211_add_hecaps(wire,&ic);
    ni={}; assert(ieee80211_setup_hecaps(&ni,wire+3,end-wire-3));
    const uint8_t op[]={0,0,0,7,0xfc,0xff};
    assert(ieee80211_setup_heop(&ni,op,sizeof(op)));
    ieee80211_channel channel={5,5180,5210,0}; ni.ni_chan=&channel;
    ni.ni_chw=IEEE80211_CHAN_WIDTH_80; ni.ni_he_requested=1;
    ni.ni_flags|=IEEE80211_NODE_HT|IEEE80211_NODE_VHT|IEEE80211_NODE_QOS;
    ni.ni_rx_nss=2; ic.ic_bss=&ni;
    ieee80211_he_negotiate(&ic,&ni); assert(ni.ni_flags & IEEE80211_NODE_HE);
    for(unsigned reason=0;reason<7;reason++) {
        auto c=ic; auto n=ni;
        if(reason==0) c.ic_flags &= ~IEEE80211_F_HEON;
        if(reason==1) n.ni_flags &= ~IEEE80211_NODE_HECAP;
        if(reason==2) n.ni_he_oper_params |= IEEE80211_HE_OPERATION_TWT_REQUIRED;
        if(reason==3) n.ni_he_mcs_nss_supp.rx_mcs_80=0xffff;
        if(reason==4) n.ni_he_oper_nss_set=0xffc0; // requires 3 streams
        if(reason==5) n.ni_he_requested=0;
        if(reason==6) {c.ic_flags|=IEEE80211_F_RSNON;n.ni_rsnciphers=IEEE80211_CIPHER_TKIP;}
        ieee80211_he_negotiate(&c,&n);
        assert(!(n.ni_flags & IEEE80211_NODE_HE));
        assert(n.ni_flags & IEEE80211_NODE_VHT);
    }
    // Live beacon updates preserve HE when an IE is omitted or truncated.
    ic.ic_state=IEEE80211_S_RUN;
    ieee80211_update_he_params(&ic,&ni,nullptr,nullptr,nullptr);
    assert((ni.ni_flags & (IEEE80211_NODE_HECAP|IEEE80211_NODE_HEOP)) ==
        (IEEE80211_NODE_HECAP|IEEE80211_NODE_HEOP));
    uint8_t truncated_op[]={255,1,36};
    ieee80211_update_he_params(&ic,&ni,wire,truncated_op,nullptr);
    assert(ni.ni_he_oper_params==(7U<<24));
    // MU EDCA records must have matching ACI order before reaching firmware.
    uint8_t mu[13]={0,0,0x43,1,32,0x54,2,64,0x65,3,96,0x76,4};
    ieee80211_update_he_params(&ic,&ni,wire,nullptr,mu);
    assert(ni.ni_flags & IEEE80211_NODE_HE_MU_EDCA);
    auto prior=ni; mu[4]=0;
    ieee80211_update_he_params(&ic,&ni,wire,nullptr,mu);
    assert(memcmp(ni.ni_he_mu_edca,prior.ni_he_mu_edca,13)==0);
    iwx_he_sta_context_cmd mu_cmd; iwx_build_he_sta(&ni,&mu_cmd);
    assert(mu_cmd.flags & IWX_HE_MU_EDCA_CW);
    assert(mu_cmd.trig_based_txf[IWX_AC_VO].mu_time==4);
    assert(mu_cmd.trig_based_txf[IWX_AC_BE].cwmin==3);
    // A new association must not reuse stale HE data from a previous AP.
    auto stale=ni;ic.ic_state=0;
    ieee80211_update_he_params(&ic,&stale,nullptr,nullptr,nullptr);
    ieee80211_he_negotiate(&ic,&stale);
    assert(!(stale.ni_flags & IEEE80211_NODE_HE));
    // AP supports only one TX stream; local RX/TX supports two. TLC must obey AP RX.
    ni.ni_he_mcs_nss_supp.rx_mcs_80=0xfffd;
    iwx_tlc_config_cmd_v4 rates={}; iwx_rs_fw_he_set_enabled_rates(&s,&rates);
    assert(rates.ht_rates[0][0]==0x3ff && rates.ht_rates[1][0]==0);
    assert(rates.ht_rates[0][1]==0);
    ni.ni_he_mcs_nss_supp.rx_mcs_80=0xfffa;
    ni.ni_he_cap_elem.phy_cap_info[1]&=~IEEE80211_HE_PHY_CAP1_LDPC_CODING_IN_PAYLOAD;
    iwx_rs_fw_he_set_enabled_rates(&s,&rates); assert(rates.ht_rates[0][0]==0x3ff);
    // Firmware byte layout, color/RTS/PE and nominal padding.
    ni.ni_he_oper_params=(7U<<24)| (321U<<4)|3;
    ni.ni_he_cap_elem.phy_cap_info[9]=IEEE80211_HE_PHY_CAP9_NOMIMAL_PKT_PADDING_16US;
    iwx_he_sta_context_cmd cmd; iwx_build_he_sta(&ni,&cmd);
    assert(cmd.bss_color==7 && cmd.frame_time_rts_th==321 && cmd.htc_trig_based_pkt_ext==3);
    assert(cmd.tid_limit==1 && (cmd.flags & IWX_HE_PACKET_EXT));
    for(auto &ss:cmd.pkt_ext)for(auto &bw:ss)assert(bw[0]==7 && bw[1]==0);
    // Intel's known PPE fixture spans byte boundaries, PPET16=0 / PPET8=7.
    uint8_t ppe[]={0x61,0x1c,0xc7,0x71}; memcpy(ni.ni_ppe_thres,ppe,4);
    ni.ni_he_cap_elem.phy_cap_info[6]|=IEEE80211_HE_PHY_CAP6_PPE_THRESHOLD_PRESENT;
    iwx_build_he_sta(&ni,&cmd);
    for(unsigned ss=0;ss<2;ss++)for(unsigned bw=2;bw<4;bw++)
        assert(cmd.pkt_ext[ss][bw][0]==7 && cmd.pkt_ext[ss][bw][1]==0);
    // Known HE rates: 80 MHz 2SS MCS11 = 1200.98 Mbps; 160 MHz = 2401.96 Mbps.
    uint32_t rate=IWX_RATE_MCS_HE_MSK|11|IWX_RATE_MCS_NSS_MSK|IWX_RATE_MCS_CHAN_WIDTH_80;
    assert(iwx_he_rate_kbps(rate)==1200980);
    rate=(rate&~IWX_RATE_MCS_CHAN_WIDTH_MSK)|IWX_RATE_MCS_CHAN_WIDTH_160;
    assert(iwx_he_rate_kbps(rate)==2401960);
    assert(iwx_he_rate_kbps(rate|IWX_RATE_MCS_HE_TYPE_TRIG)==0);
    puts("HE parsing, fallback, hardware gating, TLC/PPE encoding and bitrate checks passed");
}
''')
with tempfile.TemporaryDirectory(prefix='itlwm-he-test-') as d:
    cpp=Path(d)/'test.cpp'; binary=Path(d)/'test'; cpp.write_text('\n'.join(parts))
    subprocess.run(['clang++','-std=c++14','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
# Validate the actual bundled firmware, not a guessed version.
count=0
for path in (root/'itlwm/firmware').glob('*68.ucode'):
    data=path.read_bytes(); pos=88; version=None
    while pos+8<=len(data):
        kind,size=struct.unpack_from('<II',data,pos);pos+=8
        assert pos+size<=len(data)
        if kind==48:
            for i in range(pos,pos+size,4):
                if data[i:i+2]==bytes([7,5]): version=data[i+2]
        pos+=(size+3)&~3
    assert version==2,(path.name,version)
    count+=1
print(f'HE context v2 verified in {count} bundled firmware files')
