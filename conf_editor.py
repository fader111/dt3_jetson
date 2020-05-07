def file_edit(fname, field, new_value='192.168.0.16/24'):
    """ edit conf file changes, mask """
    if (type(fname)     is not str) | \
            (type(field)     is not str )| \
            (type(new_value) is not str ):
        print ('file_edit Bad params!')
        return False
    try:
        with open(fname, 'r') as f:
            file = f.read()
        strs = file.split('\n')
        for i, _str in enumerate(strs):
            if (field in _str) & (not '#' in _str):
                if field == 'inform':
                    strs[i] = field + ' ' + new_value
                else:
                    strs[i] = field + '=' + new_value
        out = ''
        for _str in strs:
            out+=_str+'\n'
        with open(fname, 'w') as f:
            f.write(out)
        return True
    except:
        print ('conf writing faile')
        return False

def file_edit_jetson(fname, ip, gate):
    """ edit file /etc/NetworkManager/system-connections/Wired connection 1 """
    key_val = 'address1' 
    # whole string - address1=192.168.0.190/24,192.168.0.254
    if (type(fname)     is not str) | \
        (type(ip)       is not str) | \
        (type(gate)     is not str ):
        print ('file_edit Bad params!')
        return False
    try:
        with open(fname, 'r') as f:
            file = f.read()
        strs = file.split('\n')
        for i, _str in enumerate(strs):
            if (key_val in _str) & (not '#' in _str):
                strs[i]= key_val + '=' + ip + ',' + gate
        out = ''
        for _str in strs:
            out+=_str+'\n'
        with open(fname, 'w') as f:
            f.write(out)
        return True
    except:
        print ('conf writing faile')
        return False