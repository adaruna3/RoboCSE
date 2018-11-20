import torch.nn as nn
import torch
from torch.autograd import Variable


class Analogy(nn.Module):
    def __init__(self,num_ents,num_rels,hidden_size,lmbda=0.0):
        """
        Creates an analogy model object
        :param num_ents: total number of entities
        :param num_rels: total number of relations
        :param hidden_size: dimensionality of the embedding
        :param lmbda: loss regularization for learning
        """
        super(Analogy, self).__init__()
        self.num_ents = num_ents
        self.num_rels = num_rels
        self.hidden_size = hidden_size
        self.lmbda = lmbda
        self.ent_im_embeddings = nn.Embedding(num_ents,hidden_size/2)
        self.ent_re_embeddings = nn.Embedding(num_ents,hidden_size/2)
        self.rel_re_embeddings = nn.Embedding(num_rels,hidden_size/2)
        self.rel_im_embeddings = nn.Embedding(num_rels,hidden_size/2)
        self.ent_embeddings = nn.Embedding(num_ents, hidden_size)
        self.rel_embeddings = nn.Embedding(num_rels, hidden_size)
        self.softplus = nn.Softplus()
        self.init_embeddings()

    def init_embeddings(self):
        """
        Initializes the embedding weights
        """
        nn.init.xavier_uniform_(self.ent_re_embeddings.weight.data)
        nn.init.xavier_uniform_(self.ent_im_embeddings.weight.data)
        nn.init.xavier_uniform_(self.rel_re_embeddings.weight.data)
        nn.init.xavier_uniform_(self.rel_im_embeddings.weight.data)
        nn.init.xavier_uniform_(self.ent_embeddings.weight.data)
        nn.init.xavier_uniform_(self.rel_embeddings.weight.data)

    def _calc(self,e_re_s,e_im_s,e_s,e_re_o,e_im_o,e_o,r_re,r_im,r):
        """
        Calculates the analogy score for a knowledge triple
        :param e_re_s: real part of subject (complex)
        :param e_im_s: imaginary part of subject (complex)
        :param e_s: real part of subject (distmult)
        :param e_re_o: real part of object (complex)
        :param e_im_o: imaginary part of object (complex)
        :param e_o: real part of object (distmult)
        :param r_re: real part of relation (complex)
        :param r_im: imaginary part of relation (complex)
        :param r: real part of relation (distmult)
        :return: analogy score of triple
        """
        return torch.sum(r_re * e_re_s * e_re_o +
                         r_re * e_im_s * e_im_o +
                         r_im * e_re_s * e_im_o -
                         r_im * e_im_s * e_re_o,
                         1,False) + \
               torch.sum(e_s*e_o*r,1,False)

    def forward(self,batch,labels):
        """
        Feeds a batch of triples forward through the analogy model for training
        :param batch: input batch of triples
        :param labels: labels for input batch
        :return: returns average loss over the batch
        """
        batch_s = batch[:,0]
        batch_r = batch[:,1]
        batch_o = batch[:,2]
        batch_y = Variable(torch.from_numpy(labels))
        # get the corresponding embeddings for calculations
        e_re_s = self.ent_re_embeddings(batch_s)
        e_im_s = self.ent_im_embeddings(batch_s)
        e_s = self.ent_embeddings(batch_s)
        r_re = self.rel_re_embeddings(batch_r)
        r_im = self.rel_im_embeddings(batch_r)
        r = self.rel_embeddings(batch_r)
        e_re_o = self.ent_re_embeddings(batch_o)
        e_im_o = self.ent_im_embeddings(batch_o)
        e_o = self.ent_embeddings(batch_o)
        # calculates the loss
        res = self._calc(e_re_s,e_im_s,e_s,e_re_o,e_im_o,e_o,r_re,r_im,r)
        emb_loss = torch.mean(self.softplus(- batch_y * res))
        # included regularization term
        regul = torch.mean(e_re_s**2)+torch.mean(e_im_s**2)*torch.mean(e_s**2)+\
               torch.mean(e_re_o**2)+torch.mean(e_im_o**2)+torch.mean(e_o**2)+\
               torch.mean(r_re**2)+torch.mean(r_im**2)+torch.mean(r**2)
        # calculates loss to get what the framework will optimize
        loss = emb_loss + self.lmbda*regul
        return loss

    def predict(self,batch):
        """
        Feeds a batch of triples forward through the analogy model for inference
        :param batch:
        :return:
        """
        batch_s = batch[:,0]
        batch_r = batch[:,1]
        batch_o = batch[:,2]
        # get the corresponding embeddings for calculations
        p_re_s = self.ent_re_embeddings(Variable(torch.from_numpy(batch_s)))
        p_re_o = self.ent_re_embeddings(Variable(torch.from_numpy(batch_o)))
        p_re_r = self.rel_re_embeddings(Variable(torch.from_numpy(batch_r)))
        p_im_s = self.ent_im_embeddings(Variable(torch.from_numpy(batch_s)))
        p_im_o = self.ent_im_embeddings(Variable(torch.from_numpy(batch_o)))
        p_im_r = self.rel_im_embeddings(Variable(torch.from_numpy(batch_r)))
        p_s = self.ent_im_embeddings(Variable(torch.from_numpy(batch_s)))
        p_o = self.ent_im_embeddings(Variable(torch.from_numpy(batch_o)))
        p_r = self.rel_im_embeddings(Variable(torch.from_numpy(batch_r)))
        # calculates the score
        score = -self._calc(p_re_s, p_im_s, p_s,
                              p_re_o, p_im_o, p_o,
                              p_re_r, p_im_r, p_r)
        return score.cpu()


if __name__ == "__main__":
    from datasets.data_utils import KnowledgeTriplesDataset
    from torch.utils.data import DataLoader
    import numpy as np

    # creates triples dataset
    dataset = KnowledgeTriplesDataset("demo","train")
    # creates analogy model
    model = Analogy(len(dataset.e2i),len(dataset.r2i),100)

    # loader batch loads triples for training
    batch_size = 2
    num_threads = 1
    dataset_loader = DataLoader(dataset,batch_size=batch_size,shuffle=False,
                                num_workers=num_threads)

    # loop through data printing batch number and loss
    labels = np.ones((batch_size,),np.float32) # all positive examples
    for idx_b, batch in enumerate(dataset_loader):
        loss = model.forward(batch,labels)
        print "Loss of batch " + str(idx_b) + " is " + \
              str(loss.detach().numpy())