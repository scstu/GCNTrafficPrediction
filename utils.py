import pickle
import numpy as np
import scipy.io as sio
import scipy.sparse as sp
from scipy.sparse import linalg
from sklearn import preprocessing
from scipy.sparse.linalg import eigs

class StrToBytes:
    def __init__(self, fileobj):
        self.fileobj = fileobj
    def read(self, size):
        return self.fileobj.read(size).encode()
    def readline(self, size=-1):
        return self.fileobj.readline(size).encode()

def dump_pickle(data, file):
    try:
        with open(file, 'wb') as datafile:
            pickle.dump(data, datafile)
    except Exception as e:
        raise e

def load_pickle_str2bytes(file):
    try:
        with open(file, 'r') as datafile:
            pickle.load(StrToBytes(datafile))
    except Exception as e:
        raise e

def load_pickle_rb(file):
    try:
        with open(file, 'rb') as datafile:
            data = pickle.load(datafile)
    except Exception as e:
        raise e
    return data

def load_pickle(file):
    try:
        data = load_pickle_rb(file)
    except:
        data = load_pickle_str2bytes(file)
    return data


# def get_subarea_index(n1, n2):
#     delta = n2 - n1
#     indices = []
#     for i in range(delta, delta+n1):
#         indices.append(np.arange(i*n2 + delta - 1, i*n2 + delta -1 + n1))
#     return np.concatenate(indices)



def load_npy_data(filename, split):
    if len(filename) == 2:
        d1 = np.load(filename[0])
        d2 = np.load(filename[1])
        data = np.concatenate((np.expand_dims(d1, axis=-1), np.expand_dims(d2, axis=-1)), axis=-1)
    elif len(filename) == 1:
        data = np.load(filename[0])
    train = data[0:split[0]]
    if len(split) > 2:
        validate = data[split[0]:(split[0] + split[1])]
        test = data[(split[0]+split[1]):(split[0]+split[1]+split[2])]
    else:
        validate = None
        test = data[split[0]:(split[0] + split[1])]
    return data, train, validate, test

def load_npy_data_interval_split(filename, split):
    if len(filename) == 2:
        d1 = np.load(filename[0])
        d2 = np.load(filename[1])
        data = np.concatenate((np.expand_dims(d1, axis=-1), np.expand_dims(d2, axis=-1)), axis=-1)
    elif len(filename) == 1:
        data = np.load(filename[0])
    train = data[split[0][0]:split[0][1]]
    if len(split) > 2:
        validate = data[split[1][0]:split[1][1]]
        test = data[split[2][0]:split[2][1]]
    else:
        validate = None
        test = data[split[1][0]:split[1][1]]
    return data, train, validate, test

def load_pkl_data(filename, split):
    data = load_pickle_rb(filename)
    train = data[0:split[0]]
    if len(split) > 2:
        validate = data[split[0]:(split[0] + split[1])]
        test = data[(split[0]+split[1]):(split[0]+split[1]+split[2])]
    else:
        validate = None
        test = data[split[0]:(split[0]+split[1])]
    return data, train, validate, test

def load_mat_data(filename, dataname, split):
    data = sio.loadmat(filename)[dataname]
    #
    #max_d = np.max(data[:, -2:], axis=0)
    #min_d = np.min(data[:, -2:], axis=0)
    #data[:, -2:] = (data[:, -2:] - min_d)/(max_d - min_d)
    data[:, -2:] = preprocessing.scale(data[:, -2:])
    train = data[0:split[0]]
    if len(split) > 2:
        validate = data[split[0]:(split[0] + split[1])]
        test = data[(split[0]+split[1]):(split[0]+split[1]+split[2])]
    else:
        validate = None
        test = data[split[0]:(split[0] + split[1])]
    return data, train, validate, test

def calculate_normalized_laplacian(adj):
    """
    # L = D^-1/2 (D-A) D^-1/2 = I - D^-1/2 A D^-1/2
    # D = diag(A 1)
    :param adj:
    :return:
    """
    adj = sp.coo_matrix(adj)
    d = np.array(adj.sum(1))
    d_inv_sqrt = np.power(d, -0.5).flatten()
    d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.
    d_mat_inv_sqrt = sp.diags(d_inv_sqrt)
    normalized_laplacian = sp.eye(adj.shape[0]) - adj.dot(d_mat_inv_sqrt).transpose().dot(d_mat_inv_sqrt).tocoo()
    return normalized_laplacian


def calculate_random_walk_matrix(adj_mx):
    adj_mx = sp.coo_matrix(adj_mx)
    d = np.array(adj_mx.sum(1))
    d_inv = np.power(d, -1).flatten()
    d_inv[np.isinf(d_inv)] = 0.
    d_mat_inv = sp.diags(d_inv)
    random_walk_mx = d_mat_inv.dot(adj_mx).tocoo()
    return random_walk_mx

def calculate_scaled_laplacian(adj_mx, lambda_max=2, undirected=True):
    if undirected:
        adj_mx = np.maximum.reduce([adj_mx, adj_mx.T])
    L = calculate_normalized_laplacian(adj_mx)
    if lambda_max is None:
        lambda_max, _ = linalg.eigsh(L, 1, which='LM')
        lambda_max = lambda_max[0]
    L = sp.csr_matrix(L)
    M, _ = L.shape
    I = sp.identity(M, format='csr', dtype=L.dtype)
    L = (2 / lambda_max * L) - I
    return L.astype(np.float32)

def get_rescaled_W(w, delta=1e7, epsilon=0.8):
    w2 = np.exp(-w / delta, dtype=np.float32)
    zero_index = np.eye(len(w2)) + np.array(w2 < epsilon, np.int32)
    W = w2 + zero_index * (-w2)
    return W

def scaled_laplacian(W):
    '''
    Normalized graph Laplacian function.
    :param W: np.ndarray, [n_route, n_route], weighted adjacency matrix of G.
    :return: np.matrix, [n_route, n_route].
    '''
    # d ->  diagonal degree matrix
    n, d = np.shape(W)[0], np.sum(W, axis=1)
    # L -> graph Laplacian
    L = -W
    L[np.diag_indices_from(L)] = d
    for i in range(n):
        for j in range(n):
            if (d[i] > 0) and (d[j] > 0):
                L[i, j] = L[i, j] / np.sqrt(d[i] * d[j])
    # lambda_max \approx 2.0, the largest eigenvalues of L.
    lambda_max = eigs(L, k=1, which='LR')[0][0].real
    return np.mat(2 * L / lambda_max - np.identity(n))


def get_index_for_month(year, month):
    if year=='2012' or year=='2016':
        day_sum = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    else:
        day_sum = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return np.sum(day_sum[:int(month)])

def gen_timestamps_for_year_ymd(year):
    month1 = ['0'+str(e) for e in range(1,10)]
    month2 = [str(e) for e in range(10,13)]
    month = month1+month2
    day1 = ['0'+str(e) for e in range(1,10)]
    day2 = [str(e) for e in range(10,32)]
    day = day1+day2
    if year=='2012' or year=='2016':
        day_sum = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    else:
        day_sum = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    timestamps = []
    for m in range(len(month)):
        for d in range(day_sum[m]):
            t = [year+month[m]+day[d]]
            t_d = t*24
            timestamps.append(t_d[:])
    timestamps = np.hstack(np.array(timestamps))
    return timestamps

def gen_timestamps(years, gen_timestamps_for_year=gen_timestamps_for_year_ymd):
    timestamps = []
    for y in years:
        timestamps.append(gen_timestamps_for_year(y))
    timestamps = np.hstack(np.array(timestamps))
    return timestamps

def gen_timestamps_for_year_ymdh(year):
    month1 = ['0'+str(e) for e in range(1,10)]
    month2 = [str(e) for e in range(10,13)]
    month = month1+month2
    day1 = ['0'+str(e) for e in range(1,10)]
    day2 = [str(e) for e in range(10,32)]
    day = day1+day2
    if year=='2012' or year=='2016':
        day_sum = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    else:
        day_sum = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    hour1 = ['0'+str(e) for e in range(0,10)]
    hour2 = [str(e) for e in range(10,24)]
    hour = hour1+hour2
    timestamps = []
    for m in range(len(month)):
        for d in range(day_sum[m]):
            #t = [year+month[m]+day[d]]
            t_d = []
            for h in range(24):
                t_d.append(year+month[m]+day[d]+hour[h])
            timestamps.append(t_d[:])
    timestamps = np.hstack(np.array(timestamps))
    return timestamps

def gen_timestamps_for_year_ymdhm(year):
    month1 = ['0'+str(e) for e in range(1,10)]
    month2 = [str(e) for e in range(10,13)]
    month = month1+month2
    day1 = ['0'+str(e) for e in range(1,10)]
    day2 = [str(e) for e in range(10,32)]
    day = day1+day2
    if year=='2012' or year=='2016':
        day_sum = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    else:
        day_sum = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    hour1 = ['0'+str(e) for e in range(0,10)]
    hour2 = [str(e) for e in range(10,24)]
    hour = hour1+hour2
    #minute = ['00', '10', '20', '30', '40', '50']
    minute = ['00', '30']
    timestamps = []
    for m in range(len(month)):
        for d in range(day_sum[m]):
            #t = [year+month[m]+day[d]]
            t_d = []
            for h in range(24):
                a = [year+month[m]+day[d]+hour[h]+e for e in minute]
                #t_d = [t_d.append(year+month[m]+day[d]+hour[h]+e) for e in minute]
                t_d.append(a)
            t_d = np.hstack(np.array(t_d))
            timestamps.append(t_d[:])
    timestamps = np.hstack(np.array(timestamps))
    return timestamps


def batch_data(d_data, f_data, batch_size=32, input_steps=10, output_steps=10):
    # d_data: [num, num_station, 2]
    # f_data: [num, {num_station, num_station}]
    num = d_data.shape[0]
    assert len(f_data) == num
    # x: [batches, batch_size, input_steps, num_station, 2]
    # y: [batches, batch_size, output_steps, num_station, 2]
    # f: [batches, batch_size, input_steps+output_steps, {num_station, num_station}]
    x = []
    y = []
    f = []
    i = 0
    while i<num-batch_size-input_steps-output_steps:
        batch_x = []
        batch_y = []
        batch_f = []
        for s in range(batch_size):
            batch_x.append(d_data[(i+s): (i+s+input_steps)])
            batch_y.append(d_data[(i+s+input_steps): (i+s+input_steps+output_steps)])
            batch_f.append(f_data[(i+s): (i+s+input_steps+output_steps)])
        x.append(batch_x)
        y.append(batch_y)
        f.append(batch_f)
        i += batch_size
    return x, y, f

def get_embedding_from_file(file, num):
    with open(file, 'r') as df:
        lines = df.readlines()
        _, dim = lines[0].split(' ', 1)
        #num = int(num)
        dim = int(dim)
        embeddings = np.zeros((num, dim), dtype=np.float32)
        for line in lines[1:]:
            label, v_str = line.split(' ', 1)
            v = [float(e) for e in v_str.split()]
            embeddings[int(label)] = v
    return embeddings

def get_loss(y, y_out):
    # y, y_out: [num_station, 2]
    # check-in loss
    # y = np.transpose(y)
    # y_out = np.transpose(y_out)
    y = np.clip(y, 0, None)
    y_out = np.clip(y_out, 0, None)
    in_rmse = np.sqrt(np.mean(np.square(y_out[:,0]-y[:,0])))
    out_rmse = np.sqrt(np.mean(np.square(y_out[:,1]-y[:,1])))
    in_rmlse = np.sqrt(np.mean(np.square(np.log(y_out[:,0] + 1)-np.log(y[:,0] + 1))))
    out_rmlse = np.sqrt(np.mean(np.square(np.log(y_out[:,1] + 1)-np.log(y[:,1] + 1))))
    in_sum = np.max((np.sum(y[:,0]), 1))
    out_sum = np.max((np.sum(y[:,1]), 1))
    #print in_sum.shape
    in_er = np.sum(np.abs(y_out[:,0]-y[:,0]))/in_sum
    out_er = np.sum(np.abs(y_out[:,1]-y[:,1]))/out_sum
    #print in_sum
    #print in_er
    return [in_rmse, out_rmse, in_rmlse, out_rmlse, in_er, out_er]

def get_loss_by_batch(y, y_out):
    # y, y_out: [batch_size, num_station, 2]
    # check-in loss
    y = np.clip(y, 0, None)
    y_out = np.clip(y_out, 0, None)
    in_rmse = np.sum(np.sqrt(np.mean(np.square(y_out[:,:,0]-y[:,:,0]), -1)))
    out_rmse = np.sum(np.sqrt(np.mean(np.square(y_out[:,:,1]-y[:,:,1]), -1)))
    in_rmlse = np.sum(np.sqrt(np.mean(np.square(np.log(y_out[:,:,0] + 1)-np.log(y[:,:,0] + 1)), -1)))
    out_rmlse = np.sum(np.sqrt(np.mean(np.square(np.log(y_out[:,:,1] + 1)-np.log(y[:,:,1] + 1)), -1)))
    in_sum = np.clip(np.sum(y[:,:,0], -1), 1, None)
    out_sum = np.clip(np.sum(y[:,:,1], -1), 1, None)
    #print in_sum.shape
    in_er = np.sum(np.sum(np.abs(y_out[:,:,0]-y[:,:,0]), axis=-1)/in_sum)
    out_er = np.sum(np.sum(np.abs(y_out[:,:,1]-y[:,:,1]), axis=-1)/out_sum)
    #print in_sum
    #print in_er
    return [in_rmse, out_rmse, in_rmlse, out_rmlse, in_er, out_er]
